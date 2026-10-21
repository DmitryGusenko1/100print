import uuid
from fastapi import Depends, FastAPI, HTTPException, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.config import get_settings
from app.db import get_session
from app.models import Decision, ProjectState, Task
from app.repository import add_message, owned_project
from app.schemas import DecisionCreate, MessageCreate, StateCreate, TaskCreate, TaskUpdate
from app.security import require_api_identity
from app.service import build_context

settings = get_settings()
app = FastAPI(title="AI Memory API", version="0.1.0")

@app.get("/health")
async def health(): return {"status":"ok"}

async def require_project(session, owner_id, project_id):
    row = await owned_project(session, owner_id, project_id)
    if not row: raise HTTPException(status_code=404, detail="Project not found")
    return row

@app.post("/messages")
async def create_message(payload: MessageCreate, owner_id: int = Depends(require_api_identity), session: AsyncSession = Depends(get_session)):
    await require_project(session, owner_id, payload.project_id)
    if len(payload.content) > settings.max_message_chars: raise HTTPException(status_code=413, detail="Message too large")
    row, created = await add_message(session, project_id=payload.project_id, dialogue_key=payload.dialogue_key, source=payload.source, external_id=payload.external_id, role=payload.role, content=payload.content)
    return {"id":str(row.id),"created":created}

@app.get("/projects/{project_id}/context")
async def context(project_id: uuid.UUID, q: str|None = Query(default=None,max_length=500), owner_id: int = Depends(require_api_identity), session: AsyncSession = Depends(get_session)):
    await require_project(session, owner_id, project_id)
    return await build_context(session, project_id, q)

@app.get("/projects/{project_id}/tasks")
async def tasks(project_id: uuid.UUID, owner_id: int = Depends(require_api_identity), session: AsyncSession = Depends(get_session)):
    await require_project(session, owner_id, project_id)
    rows=(await session.scalars(select(Task).where(Task.project_id==project_id).order_by(Task.created_at.desc()))).all()
    return [{"id":str(x.id),"title":x.title,"status":x.status} for x in rows]

@app.post("/tasks")
async def create_task(payload: TaskCreate, owner_id: int = Depends(require_api_identity), session: AsyncSession = Depends(get_session)):
    await require_project(session, owner_id, payload.project_id)
    row=Task(**payload.model_dump()); session.add(row); await session.commit(); await session.refresh(row)
    return {"id":str(row.id),"status":row.status}

@app.patch("/tasks/{task_id}")
async def update_task(task_id: uuid.UUID, payload: TaskUpdate, owner_id: int = Depends(require_api_identity), session: AsyncSession = Depends(get_session)):
    row=await session.get(Task,task_id)
    if not row: raise HTTPException(status_code=404,detail="Task not found")
    await require_project(session,owner_id,row.project_id); row.status=payload.status; await session.commit()
    return {"id":str(row.id),"status":row.status}

@app.post("/decisions")
async def create_decision(payload: DecisionCreate, owner_id: int = Depends(require_api_identity), session: AsyncSession = Depends(get_session)):
    await require_project(session,owner_id,payload.project_id)
    row=Decision(**payload.model_dump()); session.add(row); await session.commit(); await session.refresh(row)
    return {"id":str(row.id),"confirmed":row.confirmed}

@app.post("/states")
async def create_state(payload: StateCreate, owner_id: int = Depends(require_api_identity), session: AsyncSession = Depends(get_session)):
    await require_project(session,owner_id,payload.project_id)
    row=ProjectState(**payload.model_dump()); session.add(row); await session.commit(); await session.refresh(row)
    return {"id":str(row.id)}
