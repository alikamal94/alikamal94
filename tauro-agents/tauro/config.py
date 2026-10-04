"""Settings, read from the environment (or a .env file)."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from zoneinfo import ZoneInfo

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

KUWAIT = ZoneInfo("Asia/Kuwait")


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


@dataclass(frozen=True)
class Models:
    # Model choice follows the KNINV agent map: Opus for the judgement-heavy roles,
    # Sonnet for the makers, Haiku for the 30-minute scans.
    strategist: str = _env("TAURO_MODEL_STRATEGIST", "claude-opus-5-5")
    qa: str = _env("TAURO_MODEL_QA", "claude-opus-5-5")
    copywriter: str = _env("TAURO_MODEL_COPYWRITER", "claude-sonnet-5-5")
    market_brief: str = _env("TAURO_MODEL_MARKET_BRIEF", "claude-sonnet-5-5")
    market_scan: str = _env("TAURO_MODEL_MARKET_SCAN", "claude-haiku-4-5")


@dataclass(frozen=True)
class Settings:
    root: Path = ROOT
    knowledge_dir: Path = ROOT / "knowledge"
    assets_dir: Path = ROOT / "assets"
    out_dir: Path = Path(_env("TAURO_OUT_DIR", str(ROOT / "out")))
    db_path: Path = Path(_env("TAURO_DB_PATH", str(ROOT / "out" / "tauro.db")))
    models: Models = field(default_factory=Models)
    telegram_token: str = _env("TELEGRAM_BOT_TOKEN")
    telegram_approver_chat_id: str = _env("TELEGRAM_APPROVER_CHAT_ID")
    telegram_backup_chat_id: str = _env("TELEGRAM_BACKUP_CHAT_ID")
    chromium_path: str = _env("TAURO_CHROMIUM_PATH")  # optional: use a specific Chromium build
    price_provider: str = _env("TAURO_PRICE_PROVIDER", "sample")  # sample | mt5
    max_qa_retries: int = int(_env("TAURO_MAX_QA_RETRIES", "2"))
    monthly_budget_usd: float = float(_env("TAURO_MONTHLY_BUDGET_USD", "250"))


settings = Settings()
