from app.config import get_settings
from app.repository import get_context
settings = get_settings()

def message_dict(x): return {"id": str(x.id), "role": x.role, "content": x.content, "created_at": x.created_at.isoformat()}
def task_dict(x): return {"id": str(x.id), "title": x.title, "status": x.status}
def decision_dict(x): return {"id": str(x.id), "text": x.text, "confirmed": x.confirmed}

async def build_context(session, project_id, query=None):
    state, recent, relevant, tasks, decisions = await get_context(session, project_id, query, settings.context_message_limit, settings.context_search_limit)
    return {
        "project_id": str(project_id),
        "state": state.summary if state else None,
        "recent_messages": [message_dict(x) for x in recent],
        "relevant_messages": [message_dict(x) for x in relevant],
        "tasks": [task_dict(x) for x in tasks],
        "decisions": [decision_dict(x) for x in decisions],
    }
