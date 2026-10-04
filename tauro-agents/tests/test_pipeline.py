"""End-to-end pipeline with fake agents: no Claude API key or Telegram token needed."""
from tauro.agents.designer import DesignerAgent
from tauro.agents.qa import QAAgent
from tauro.approvals import FileApprover
from tauro.data.prices import SampleProvider
from tauro.orchestrator import Orchestrator
from tauro.render.renderer import Renderer
from tauro.storage import Store


class FakeCopywriter:
    """Returns the sample copy; the first `bad` calls contain a banned phrase."""

    def __init__(self, copy, bad=0):
        self.copy, self.bad, self.calls, self.feedback = copy, bad, 0, []

    def run(self, brief, feedback=None):
        self.calls += 1
        self.feedback.append(feedback)
        c = self.copy.model_copy(deep=True)
        if self.calls <= self.bad:
            c.caption += " أرباح مضمونة"
        return c


def make(tmp_path, copywriter):
    store = Store(":memory:")
    orch = Orchestrator(store=store, market=None, strategist=None, copywriter=copywriter,
                        designer=DesignerAgent(Renderer(SampleProvider()), tmp_path / "posts"),
                        qa=QAAgent(llm=None), approver=FileApprover(tmp_path), max_retries=2)
    return orch, store


def test_clean_post_goes_to_ali(sample, tmp_path):
    brief, copy = sample("news_card")
    orch, store = make(tmp_path, FakeCopywriter(copy))
    result = orch.produce_post(brief)
    assert result.status == "sent" and result.attempts == 1
    assert (tmp_path / "approvals" / f"{brief.brief_id}.md").exists()
    # Re-running the same brief is safe: it is not sent twice.
    assert orch.produce_post(brief).status == "skipped"


def test_qa_failure_goes_back_to_copywriter_with_reasons(sample, tmp_path):
    brief, copy = sample("news_card")
    cw = FakeCopywriter(copy, bad=1)
    orch, store = make(tmp_path, cw)
    result = orch.produce_post(brief)
    assert result.status == "sent" and result.attempts == 2
    assert any("banned phrase" in r for r in cw.feedback[1])


def test_third_failure_escalates_to_ali(sample, tmp_path):
    brief, copy = sample("news_card")
    cw = FakeCopywriter(copy, bad=99)
    orch, store = make(tmp_path, cw)
    result = orch.produce_post(brief)
    assert result.status == "escalated" and result.attempts == 3  # first try + 2 retries
    assert cw.calls == 3
    card = (tmp_path / "approvals" / f"{brief.brief_id}.md").read_text(encoding="utf-8")
    assert "needs your decision" in card


def test_sample_price_data_never_passes(sample, tmp_path):
    brief, copy = sample("gold_chart")
    cw = FakeCopywriter(copy)
    orch, store = make(tmp_path, cw)
    result = orch.produce_post(brief)
    assert result.status == "escalated"
    assert cw.calls == 1  # not the copywriter's fault, so no rewrite
    assert any("SAMPLE" in r for r in result.reasons)


def test_kill_switch():
    store = Store(":memory:")
    assert not store.publishing_paused()
    store.set_flag("kill_switch", "on")
    assert store.publishing_paused()
