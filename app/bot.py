import logging
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes, MessageHandler, filters
from app.ai import generate_reply
from app.config import get_settings
from app.db import SessionLocal
from app.repository import add_message, get_active_project, get_or_create_owner, list_projects, set_active_project
from app.security import telegram_allowed
from app.service import build_context

settings=get_settings(); log=logging.getLogger(__name__)
async def guard(update): return bool(update.effective_user and telegram_allowed(update.effective_user.id))

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update): return
    async with SessionLocal() as s:
        owner=await get_or_create_owner(s,update.effective_user.id,settings.default_project_name); project=await get_active_project(s,owner)
    await update.message.reply_text(f"Готов. Активный проект: {project.name}")

async def projects(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update): return
    async with SessionLocal() as s:
        await get_or_create_owner(s,update.effective_user.id,settings.default_project_name); rows=await list_projects(s,update.effective_user.id)
    await update.message.reply_text("\n".join(f"{p.id} — {p.name}" for p in rows) or "Проектов нет")

async def project(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update): return
    if not context.args: await update.message.reply_text("Использование: /project <UUID>"); return
    async with SessionLocal() as s:
        owner=await get_or_create_owner(s,update.effective_user.id,settings.default_project_name); rows=await list_projects(s,update.effective_user.id)
        match=next((p for p in rows if str(p.id)==context.args[0]),None)
        if not match: await update.message.reply_text("Проект не найден"); return
        await set_active_project(s,owner,match)
    await update.message.reply_text(f"Активный проект: {match.name}")

async def status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update): return
    async with SessionLocal() as s:
        owner=await get_or_create_owner(s,update.effective_user.id,settings.default_project_name); project=await get_active_project(s,owner)
    await update.message.reply_text(f"OK. Проект: {project.name}")

async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await guard(update) or not update.message or not update.message.text: return
    uid=update.effective_user.id; chat=update.effective_chat.id; ext=f"{chat}:{update.message.message_id}"; dialogue=f"telegram:{chat}"
    async with SessionLocal() as s:
        owner=await get_or_create_owner(s,uid,settings.default_project_name); project=await get_active_project(s,owner)
        incoming,created=await add_message(s,project_id=project.id,dialogue_key=dialogue,source="telegram",external_id=ext,role="user",content=update.message.text)
        if not created: return
        ctx=await build_context(s,project.id,update.message.text)
    try:
        reply=await generate_reply(ctx,update.message.text)
    except Exception:
        log.exception("AI request failed"); await update.message.reply_text("Сообщение сохранено, но AI сейчас не ответил."); return
    async with SessionLocal() as s:
        await add_message(s,project_id=project.id,dialogue_key=dialogue,source="telegram-ai",external_id=f"reply:{incoming.id}",role="assistant",content=reply)
    try:
        await update.message.reply_text(reply)
    except Exception:
        log.exception("Telegram send failed"); raise

def build_application():
    if not settings.telegram_bot_token: raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    app=Application.builder().token(settings.telegram_bot_token).build()
    app.add_handler(CommandHandler("start",start)); app.add_handler(CommandHandler("projects",projects)); app.add_handler(CommandHandler("project",project)); app.add_handler(CommandHandler("status",status))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND,on_text)); return app

def main():
    logging.basicConfig(level=logging.INFO,format="%(asctime)s %(levelname)s %(name)s %(message)s")
    build_application().run_polling()

if __name__=="__main__": main()
