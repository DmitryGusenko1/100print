import uuid
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError
from app.models import Decision, Dialogue, Message, Owner, Project, ProjectState, Task

async def get_or_create_owner(session: AsyncSession, telegram_id: int, default_project_name: str):
    owner = await session.scalar(select(Owner).where(Owner.telegram_id == telegram_id))
    if owner:
        return owner
    owner = Owner(telegram_id=telegram_id)
    session.add(owner)
    await session.flush()
    project = Project(owner_id=owner.id, name=default_project_name)
    session.add(project)
    await session.flush()
    owner.active_project_id = project.id
    await session.commit()
    await session.refresh(owner)
    return owner

async def owned_project(session: AsyncSession, telegram_id: int, project_id: uuid.UUID):
    return await session.scalar(select(Project).join(Owner, Project.owner_id == Owner.id).where(Project.id == project_id, Owner.telegram_id == telegram_id))

async def list_projects(session: AsyncSession, telegram_id: int):
    return (await session.scalars(select(Project).join(Owner, Project.owner_id == Owner.id).where(Owner.telegram_id == telegram_id).order_by(Project.created_at))).all()

async def get_active_project(session: AsyncSession, owner: Owner):
    project = await session.get(Project, owner.active_project_id) if owner.active_project_id else None
    return project or await session.scalar(select(Project).where(Project.owner_id == owner.id).order_by(Project.created_at).limit(1))

async def set_active_project(session: AsyncSession, owner: Owner, project: Project):
    owner.active_project_id = project.id
    await session.commit()

async def get_or_create_dialogue(session: AsyncSession, project_id: uuid.UUID, external_key: str):
    row = await session.scalar(select(Dialogue).where(Dialogue.project_id == project_id, Dialogue.external_key == external_key))
    if row:
        return row
    row = Dialogue(project_id=project_id, external_key=external_key)
    session.add(row)
    await session.flush()
    return row

async def add_message(session: AsyncSession, *, project_id, dialogue_key, source, external_id, role, content):
    existing = await session.scalar(select(Message).where(Message.source == source, Message.external_id == external_id))
    if existing:
        return existing, False
    dialogue = await get_or_create_dialogue(session, project_id, dialogue_key)
    row = Message(project_id=project_id, dialogue_id=dialogue.id, source=source, external_id=external_id, role=role, content=content)
    session.add(row)
    try:
        await session.commit()
    except IntegrityError:
        await session.rollback()
        return await session.scalar(select(Message).where(Message.source == source, Message.external_id == external_id)), False
    await session.refresh(row)
    return row, True

async def get_context(session: AsyncSession, project_id, query, recent_limit, search_limit):
    recent = (await session.scalars(select(Message).where(Message.project_id == project_id).order_by(desc(Message.created_at)).limit(recent_limit))).all()
    relevant = []
    if query:
        tsquery = func.plainto_tsquery("simple", query)
        relevant = (await session.scalars(select(Message).where(Message.project_id == project_id, func.to_tsvector("simple", Message.content).op("@@")(tsquery)).order_by(desc(func.ts_rank(func.to_tsvector("simple", Message.content), tsquery))).limit(search_limit))).all()
    state = await session.scalar(select(ProjectState).where(ProjectState.project_id == project_id).order_by(desc(ProjectState.created_at)).limit(1))
    tasks = (await session.scalars(select(Task).where(Task.project_id == project_id).order_by(desc(Task.created_at)).limit(50))).all()
    decisions = (await session.scalars(select(Decision).where(Decision.project_id == project_id).order_by(desc(Decision.created_at)).limit(50))).all()
    return state, list(reversed(recent)), relevant, tasks, decisions
