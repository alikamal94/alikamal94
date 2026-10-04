"""Orchestrator: plain code, no AI. Triggers each agent on schedule, passes the handoffs, logs everything."""
from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from .agents.copywriter import CopywriterAgent
from .agents.designer import DesignerAgent
from .agents.market_intel import MarketIntelAgent
from .agents.qa import QAAgent
from .agents.strategist import StrategistAgent
from .approvals import Approver, FileApprover, TelegramApprover
from .config import KUWAIT, settings
from .data.prices import get_provider
from .llm import LLM, AgentError
from .render.renderer import Renderer
from .schemas import Brief, MarketBrief, Priority, QAVerdict
from .storage import Store

log = logging.getLogger("tauro.orchestrator")


@dataclass
class PostResult:
    brief_id: str
    status: str  # sent | escalated | skipped | error
    attempts: int
    reasons: list[str]


class Orchestrator:
    def __init__(self, *, store: Store, market: MarketIntelAgent | None, strategist: StrategistAgent | None,
                 copywriter: CopywriterAgent, designer: DesignerAgent, qa: QAAgent, approver: Approver,
                 max_retries: int = 2) -> None:
        self.store, self.market, self.strategist = store, market, strategist
        self.copywriter, self.designer, self.qa, self.approver = copywriter, designer, qa, approver
        self.max_retries = max_retries

    @classmethod
    def from_settings(cls) -> "Orchestrator":
        store = Store(settings.db_path)
        llm = LLM(audit=store.audit)
        prices = get_provider(settings.price_provider)
        if settings.telegram_token and settings.telegram_approver_chat_id:
            approver: Approver = TelegramApprover(settings.telegram_token, settings.telegram_approver_chat_id)
        else:
            log.warning("TELEGRAM_BOT_TOKEN / TELEGRAM_APPROVER_CHAT_ID not set: approval cards go to %s/approvals",
                        settings.out_dir)
            approver = FileApprover(settings.out_dir)
        return cls(store=store, market=MarketIntelAgent(llm, prices), strategist=StrategistAgent(llm),
                   copywriter=CopywriterAgent(llm), designer=DesignerAgent(Renderer(prices), settings.out_dir / "posts"),
                   qa=QAAgent(llm), approver=approver, max_retries=settings.max_qa_retries)

    # ---- one post: Copywriter → Designer → QA (max retries) → Ali ----
    def produce_post(self, brief: Brief, feedback: list[str] | None = None) -> PostResult:
        if not feedback and "sent_for_approval" in self.store.stages(brief.brief_id):
            return PostResult(brief.brief_id, "skipped", 0, ["already sent for approval"])  # safe to re-run
        self.store.save(brief.brief_id, "brief", brief)
        try:
            copy = self.copywriter.run(brief, feedback=feedback)
        except AgentError as e:
            self._escalate(brief.brief_id, f"Copywriter failed: {e}")
            return PostResult(brief.brief_id, "error", 0, [str(e)])

        verdict: QAVerdict | None = None
        for attempt in range(1, self.max_retries + 2):
            self.store.save(brief.brief_id, "copy", copy, attempt)
            try:
                design, sample = self.designer.run(brief, copy)
            except Exception as e:  # rendering problems go to Ali with the reason
                self._escalate(brief.brief_id, f"Designer failed: {e}")
                return PostResult(brief.brief_id, "error", attempt, [str(e)])
            self.store.save(brief.brief_id, "design", design, attempt)
            try:
                verdict = self.qa.run(brief, copy, design, sample_data=sample)
            except AgentError as e:
                self._escalate(brief.brief_id, f"QA failed to run: {e}")
                return PostResult(brief.brief_id, "error", attempt, [str(e)])
            self.store.save(brief.brief_id, "qa", verdict, attempt)

            if verdict.verdict == "pass":
                self.approver.send(brief, copy, design, verdict)
                self.store.save(brief.brief_id, "sent_for_approval", {"attempt": attempt})
                return PostResult(brief.brief_id, "sent", attempt, [])
            if verdict.blame == "none" or attempt > self.max_retries:
                break  # nothing an agent can fix (e.g. sample data) or out of retries
            if verdict.blame == "designer":
                break  # rendering is deterministic: a re-render gives the same image, so a person must look
            try:
                copy = self.copywriter.run(brief, feedback=verdict.reasons)
            except AgentError as e:
                self._escalate(brief.brief_id, f"Copywriter retry failed: {e}")
                return PostResult(brief.brief_id, "error", attempt, [str(e)])

        assert verdict is not None
        note = f"QA failed after {attempt} attempt(s); needs your decision."
        self.approver.send(brief, copy, design, verdict, note=note)
        self.store.save(brief.brief_id, "escalated", {"attempt": attempt, "reasons": verdict.reasons})
        return PostResult(brief.brief_id, "escalated", attempt, verdict.reasons)

    def _escalate(self, brief_id: str, text: str) -> None:
        log.error("%s: %s", brief_id, text)
        self.store.save(brief_id, "error", {"message": text})
        self.approver.notify(f"⚠️ {brief_id}: {text}")

    # ---- batches ----
    def run_batch(self, batch: str, now: datetime | None = None) -> list[PostResult]:
        now = now or datetime.now(KUWAIT)
        date = now.strftime("%Y-%m-%d")
        market = self._market_brief(date, now)
        if self.strategist is None:
            raise RuntimeError("no strategist configured")
        plan = self.strategist.run(date, batch, market)
        self.store.save(f"{date}-{batch}", "plan", plan)
        results = [self.produce_post(b) for b in sorted(plan.briefs, key=lambda b: b.priority != Priority.breaking)]
        log.info("%s %s: %s", date, batch, [(r.brief_id, r.status) for r in results])
        return results

    def _market_brief(self, date: str, now: datetime) -> MarketBrief | None:
        cached = self.store.latest(date, "market_brief")  # refreshed by the 06:00 and 12:00 jobs
        if cached:
            return MarketBrief.model_validate(cached)
        if self.market is None:
            return None
        brief = self.market.run("brief", now)
        self.store.save(date, "market_brief", brief)
        return brief

    def scan(self, now: datetime | None = None) -> None:
        """30-minute scan; a breaking item fast-tracks a reactive post through 2 → 3/4 → 5 → Ali."""
        now = now or datetime.now(KUWAIT)
        if self.market is None or self.strategist is None:
            return
        result = self.market.run("scan", now)
        if not result.breaking:
            return
        date = now.strftime("%Y-%m-%d")
        self.store.save(date, "breaking", result)
        self.approver.notify("🚨 Breaking: " + result.summary_ar)
        plan = self.strategist.run(date, "breaking", result, extra="Plan exactly one reactive post with priority breaking.")
        for b in plan.briefs[:1]:
            self.produce_post(b)

    def apply_edits(self) -> None:
        """Ali tapped Edit and sent a note: rewrite with his note and send it back through QA."""
        rows = self.store.db.execute(
            "SELECT brief_id, note FROM approvals a WHERE decision='edit' AND note != '' AND id = "
            "(SELECT MAX(id) FROM approvals WHERE brief_id=a.brief_id)").fetchall()
        for row in rows:
            if self.store.flag(f"edit_done:{row['brief_id']}:{row['note']}") == "1":
                continue
            data = self.store.latest(row["brief_id"], "brief")
            if data:
                self.produce_post(Brief.model_validate(data), feedback=[f"Ali's edit note: {row['note']}"])
            self.store.set_flag(f"edit_done:{row['brief_id']}:{row['note']}", "1")

    # ---- schedule (Kuwait time) ----
    def run_forever(self) -> None:
        from apscheduler.schedulers.blocking import BlockingScheduler

        sched = BlockingScheduler(timezone=KUWAIT)
        sched.add_job(lambda: self._safe(self._market_brief_now), "cron", hour=6, minute=0, id="market_brief")
        sched.add_job(lambda: self._safe(self.run_batch, "morning"), "cron", hour=7, minute=0, id="morning")
        sched.add_job(lambda: self._safe(self._market_brief_now), "cron", hour=12, minute=0, id="midday_update")
        sched.add_job(lambda: self._safe(self.run_batch, "afternoon"), "cron", hour=14, minute=0, id="afternoon")
        sched.add_job(lambda: self._safe(self.scan), "cron", hour="6-21", minute="15,45", id="scan")
        sched.add_job(lambda: self._safe(self.apply_edits), "interval", minutes=5, id="edits")
        log.info("scheduler started (Asia/Kuwait)")
        sched.start()

    def _market_brief_now(self) -> None:
        now = datetime.now(KUWAIT)
        if self.market:
            self.store.save(now.strftime("%Y-%m-%d"), "market_brief", self.market.run("brief", now))

    def _safe(self, fn, *args) -> None:
        try:
            fn(*args)
        except Exception as e:  # one failed job must not stop the scheduler
            log.exception("job failed")
            try:
                self.approver.notify(f"⚠️ Scheduled job failed: {e}")
            except Exception:
                log.exception("could not notify")
