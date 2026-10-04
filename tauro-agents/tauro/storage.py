"""Storage and audit log. SQLite for now; the same tables move to Postgres for production.

Every handoff, prompt, model output, QA verdict and approval is kept, keyed by brief_id.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA = """
CREATE TABLE IF NOT EXISTS handoffs (
  id INTEGER PRIMARY KEY, brief_id TEXT NOT NULL, stage TEXT NOT NULL, attempt INTEGER NOT NULL DEFAULT 1,
  payload TEXT NOT NULL, created_at TEXT NOT NULL);
CREATE INDEX IF NOT EXISTS handoffs_brief ON handoffs(brief_id, stage);
CREATE TABLE IF NOT EXISTS audit (
  id INTEGER PRIMARY KEY, agent TEXT, model TEXT, brief_id TEXT, task TEXT, output TEXT, usage TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS approvals (
  id INTEGER PRIMARY KEY, brief_id TEXT NOT NULL, decision TEXT NOT NULL, note TEXT, approver TEXT, created_at TEXT);
CREATE TABLE IF NOT EXISTS publish_log (
  id INTEGER PRIMARY KEY, brief_id TEXT, channel TEXT, external_id TEXT, published_at TEXT);
CREATE TABLE IF NOT EXISTS flags (name TEXT PRIMARY KEY, value TEXT NOT NULL);
"""


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path | str) -> None:
        if str(path) != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(str(path), check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(SCHEMA)

    def save(self, brief_id: str, stage: str, payload: Any, attempt: int = 1) -> None:
        data = payload.model_dump_json() if hasattr(payload, "model_dump_json") else json.dumps(payload, ensure_ascii=False)
        self.db.execute("INSERT INTO handoffs(brief_id, stage, attempt, payload, created_at) VALUES (?,?,?,?,?)",
                        (brief_id, stage, attempt, data, now()))
        self.db.commit()

    def latest(self, brief_id: str, stage: str) -> dict | None:
        row = self.db.execute("SELECT payload FROM handoffs WHERE brief_id=? AND stage=? ORDER BY id DESC LIMIT 1",
                              (brief_id, stage)).fetchone()
        return json.loads(row["payload"]) if row else None

    def stages(self, brief_id: str) -> list[str]:
        return [r["stage"] for r in self.db.execute("SELECT stage FROM handoffs WHERE brief_id=? ORDER BY id", (brief_id,))]

    def audit(self, **row: Any) -> None:
        self.db.execute("INSERT INTO audit(agent, model, brief_id, task, output, usage, created_at) VALUES (?,?,?,?,?,?,?)",
                        (row["agent"], row["model"], row.get("brief_id", ""), row["task"], row["output"], row["usage"], now()))
        self.db.commit()

    def record_approval(self, brief_id: str, decision: str, note: str = "", approver: str = "") -> None:
        self.db.execute("INSERT INTO approvals(brief_id, decision, note, approver, created_at) VALUES (?,?,?,?,?)",
                        (brief_id, decision, note, approver, now()))
        self.db.commit()

    def decision(self, brief_id: str) -> str | None:
        row = self.db.execute("SELECT decision FROM approvals WHERE brief_id=? ORDER BY id DESC LIMIT 1", (brief_id,)).fetchone()
        return row["decision"] if row else None

    def set_flag(self, name: str, value: str) -> None:
        self.db.execute("INSERT INTO flags(name, value) VALUES (?,?) ON CONFLICT(name) DO UPDATE SET value=excluded.value",
                        (name, value))
        self.db.commit()

    def flag(self, name: str, default: str = "") -> str:
        row = self.db.execute("SELECT value FROM flags WHERE name=?", (name,)).fetchone()
        return row["value"] if row else default

    def publishing_paused(self) -> bool:
        """Kill switch: checked before every publish."""
        return self.flag("kill_switch", "off") == "on"
