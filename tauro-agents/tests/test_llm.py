from types import SimpleNamespace

import pytest

from tauro.llm import LLM, AgentError
from tauro.schemas import QAVerdict


class FakeMessages:
    def __init__(self, stop_reason="end_turn"):
        self.kwargs, self.stop_reason = None, stop_reason

    def parse(self, **kwargs):
        self.kwargs = kwargs
        usage = SimpleNamespace(input_tokens=10, cache_read_input_tokens=0, cache_creation_input_tokens=0, output_tokens=5)
        return SimpleNamespace(stop_reason=self.stop_reason, stop_details=None, model=kwargs["model"], usage=usage,
                               content=[], parsed_output=QAVerdict(brief_id="x", verdict="pass"))


def client(stop_reason="end_turn"):
    return SimpleNamespace(beta=SimpleNamespace(messages=FakeMessages(stop_reason)))


def call(llm, model):
    return llm.structured(agent="t", model=model, role="role", knowledge="kb", task="task", schema=QAVerdict)


def test_opus_request_shape():
    c = client()
    audit = []
    out = call(LLM(c, audit=lambda **row: audit.append(row)), "claude-opus-5-5")
    k = c.beta.messages.kwargs
    assert out.verdict == "pass"
    assert k["thinking"] == {"type": "adaptive"}
    assert k["output_config"] == {"effort": "medium"}
    assert k["fallbacks"] == "default"
    assert k["system"][1]["cache_control"] == {"type": "ephemeral"}  # knowledge base is cached
    assert audit and audit[0]["agent"] == "t"


def test_haiku_has_no_thinking_or_effort():
    c = client()
    call(LLM(c), "claude-haiku-4-5")
    k = c.beta.messages.kwargs
    assert "thinking" not in k and "output_config" not in k and "fallbacks" not in k


def test_refusal_raises():
    with pytest.raises(AgentError):
        call(LLM(client("refusal")), "claude-opus-5-5")
