"""Human in the loop: every passed post goes to Ali with Approve / Edit / Reject.

TelegramApprover is used once TELEGRAM_BOT_TOKEN and TELEGRAM_APPROVER_CHAT_ID are set.
Until then FileApprover writes each approval card to out/approvals/ so the pipeline can run end to end.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Protocol

from .schemas import Brief, Copy, DesignOutput, QAVerdict


class Approver(Protocol):
    def send(self, brief: Brief, copy: Copy, design: DesignOutput, verdict: QAVerdict, note: str = "") -> None: ...

    def notify(self, text: str) -> None: ...


def card_text(brief: Brief, copy: Copy, verdict: QAVerdict, note: str = "") -> str:
    lines = [f"🆔 {brief.brief_id} · {brief.template.value} · {brief.publish_at[11:16]} · {', '.join(c.value for c in brief.channels)}"]
    if brief.priority.value == "breaking":
        lines.insert(0, "🚨 BREAKING — fast track")
    if note:
        lines.append(f"⚠️ {note}")
    if verdict.verdict == "fail":
        lines.append("❌ QA: " + "; ".join(verdict.reasons))
    lines += ["", copy.caption, "", " ".join(copy.hashtags)]
    if copy.hooks:
        lines += ["", "Hooks:", *[f"• {h}" for h in copy.hooks]]
    if copy.telegram_text:
        lines += ["", "Telegram:", copy.telegram_text]
    return "\n".join(lines)


class FileApprover:
    def __init__(self, out_dir: Path) -> None:
        self.dir = out_dir / "approvals"
        self.dir.mkdir(parents=True, exist_ok=True)

    def send(self, brief: Brief, copy: Copy, design: DesignOutput, verdict: QAVerdict, note: str = "") -> None:
        images = "\n".join(f"![]({Path(p).resolve().as_uri()})" for p in design.images)
        (self.dir / f"{brief.brief_id}.md").write_text(f"{card_text(brief, copy, verdict, note)}\n\n{images}\n", encoding="utf-8")

    def notify(self, text: str) -> None:
        with (self.dir / "_notifications.log").open("a", encoding="utf-8") as f:
            f.write(text + "\n---\n")


class TelegramApprover:
    def __init__(self, token: str, chat_id: str) -> None:
        self.token, self.chat_id = token, chat_id

    async def _send(self, brief: Brief, copy: Copy, design: DesignOutput, verdict: QAVerdict, note: str) -> None:
        from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup, InputMediaPhoto

        async with Bot(self.token) as bot:
            paths = design.images[:10]
            if len(paths) == 1:
                with open(paths[0], "rb") as f:
                    await bot.send_photo(self.chat_id, f)
            else:
                media = [InputMediaPhoto(open(p, "rb")) for p in paths]
                await bot.send_media_group(self.chat_id, media)
            if verdict.verdict == "pass":
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("✅ Approve", callback_data=f"approve:{brief.brief_id}"),
                    InlineKeyboardButton("✏️ Edit", callback_data=f"edit:{brief.brief_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject:{brief.brief_id}"),
                ]])
            else:
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("✏️ Edit", callback_data=f"edit:{brief.brief_id}"),
                    InlineKeyboardButton("❌ Reject", callback_data=f"reject:{brief.brief_id}"),
                ]])
            await bot.send_message(self.chat_id, card_text(brief, copy, verdict, note)[:4000], reply_markup=keyboard)

    def send(self, brief: Brief, copy: Copy, design: DesignOutput, verdict: QAVerdict, note: str = "") -> None:
        asyncio.run(self._send(brief, copy, design, verdict, note))

    def notify(self, text: str) -> None:
        from telegram import Bot

        async def go() -> None:
            async with Bot(self.token) as bot:
                await bot.send_message(self.chat_id, text[:4000])

        asyncio.run(go())
