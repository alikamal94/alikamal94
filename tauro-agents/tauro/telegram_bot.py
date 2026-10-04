"""Telegram approval bot: Ali taps Approve / Edit / Reject on each card.

Run it as its own process next to the scheduler:  python -m tauro bot
Only the approver (and the named backup approver) can press the buttons.
"""
from __future__ import annotations

import logging

from .config import settings
from .storage import Store

log = logging.getLogger("tauro.bot")


def main() -> None:
    from telegram import Update
    from telegram.ext import Application, CallbackQueryHandler, ContextTypes, MessageHandler, filters

    if not settings.telegram_token:
        raise SystemExit("Set TELEGRAM_BOT_TOKEN (and TELEGRAM_APPROVER_CHAT_ID) in .env first")
    store = Store(settings.db_path)
    allowed = {c for c in (settings.telegram_approver_chat_id, settings.telegram_backup_chat_id) if c}

    def is_allowed(update: Update) -> bool:
        return str(update.effective_chat.id) in allowed

    async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        q = update.callback_query
        if not is_allowed(update):
            await q.answer("Not allowed", show_alert=True)
            return
        decision, brief_id = q.data.split(":", 1)
        who = q.from_user.full_name if q.from_user else ""
        if decision == "edit":
            context.chat_data["editing"] = brief_id
            store.record_approval(brief_id, "edit", "", who)
            await q.answer()
            await q.message.reply_text(f"✏️ {brief_id}: send your edit note as the next message.")
            return
        store.record_approval(brief_id, decision, "", who)
        await q.answer("Saved")
        label = {"approve": "✅ Approved — queued for publishing", "reject": "❌ Rejected — logged"}[decision]
        await q.edit_message_reply_markup(None)
        await q.message.reply_text(f"{label}: {brief_id}")

    async def on_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not is_allowed(update):
            return
        brief_id = context.chat_data.pop("editing", None)
        if not brief_id:
            await update.message.reply_text(f"Your chat id is {update.effective_chat.id}. Tap Edit on a post to send a note.")
            return
        who = update.effective_user.full_name if update.effective_user else ""
        store.record_approval(brief_id, "edit", update.message.text, who)
        await update.message.reply_text(f"Got it. {brief_id} goes back to the makers with your note.")

    async def whoami(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        # Lets Ali find his chat id before TELEGRAM_APPROVER_CHAT_ID is set.
        await update.message.reply_text(f"Your chat id is {update.effective_chat.id}")

    async def on_any_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if allowed:
            await on_text(update, context)
        else:
            await whoami(update, context)

    app = Application.builder().token(settings.telegram_token).build()
    app.add_handler(CallbackQueryHandler(on_button, pattern=r"^(approve|edit|reject):"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND & filters.ChatType.PRIVATE,
                                   on_any_text))
    log.info("approval bot running")
    app.run_polling()
