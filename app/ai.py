from openai import AsyncOpenAI
from app.config import get_settings
settings = get_settings()

def context_to_text(context):
    parts = []
    if context.get("state"): parts.append("PROJECT STATE:\n" + context["state"])
    confirmed = [d for d in context.get("decisions", []) if d.get("confirmed")]
    if confirmed: parts.append("CONFIRMED DECISIONS:\n" + "\n".join("- " + d["text"] for d in confirmed))
    if context.get("tasks"): parts.append("TASKS:\n" + "\n".join(f"- [{t['status']}] {t['title']}" for t in context["tasks"]))
    if context.get("recent_messages"): parts.append("RECENT:\n" + "\n".join(f"{m['role']}: {m['content']}" for m in context["recent_messages"]))
    if context.get("relevant_messages"): parts.append("RELEVANT:\n" + "\n".join(f"{m['role']}: {m['content']}" for m in context["relevant_messages"]))
    return "\n\n".join(parts)

async def generate_reply(context, user_text):
    if not settings.ai_api_key:
        raise RuntimeError("AI_API_KEY is not configured")
    client = AsyncOpenAI(api_key=settings.ai_api_key, base_url=settings.ai_base_url)
    response = await client.chat.completions.create(
        model=settings.ai_model,
        messages=[
            {"role":"system","content":"Use persistent project memory. Never claim an action succeeded unless it actually did."},
            {"role":"system","content":context_to_text(context)},
            {"role":"user","content":user_text},
        ],
    )
    return response.choices[0].message.content or ""
