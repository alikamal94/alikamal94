"""One wrapper for every Claude call: structured output, prompt caching, refusals, audit log."""
from __future__ import annotations

import json
import logging
from typing import Any, TypeVar

import anthropic
from pydantic import BaseModel

log = logging.getLogger("tauro.llm")
T = TypeVar("T", bound=BaseModel)

# Server-side fallback routes a declined request to another model inside the same call.
FALLBACK_BETA = "server-side-fallback-2026-07-01"


class AgentError(RuntimeError):
    pass


def web_search_tool(model: str, max_uses: int = 5) -> dict[str, Any]:
    if model.startswith("claude-haiku"):
        return {"type": "web_search_20250305", "name": "web_search", "max_uses": max_uses}
    return {"type": "web_search_20260209", "name": "web_search", "max_uses": max_uses}


class LLM:
    def __init__(self, client: anthropic.Anthropic | None = None, audit=None) -> None:
        self.client = client or anthropic.Anthropic()
        self.audit = audit  # callable(agent, model, request_summary, output_json, usage) or None

    def structured(
        self,
        *,
        agent: str,
        model: str,
        role: str,
        knowledge: str,
        task: str,
        schema: type[T],
        effort: str = "medium",
        tools: list[dict[str, Any]] | None = None,
        images: list[dict[str, Any]] | None = None,
        brief_id: str = "",
    ) -> T:
        """Run one agent step and return validated output.

        The system prompt is role + knowledge base, which is identical across runs, so it is cached;
        the per-run task goes in the user turn after it.
        """
        is_haiku = model.startswith("claude-haiku")
        kwargs: dict[str, Any] = dict(
            model=model,
            max_tokens=16000,
            system=[
                {"type": "text", "text": role},
                {"type": "text", "text": knowledge, "cache_control": {"type": "ephemeral"}},
            ],
            messages=[{"role": "user", "content": [*(images or []), {"type": "text", "text": task}]}],
            output_format=schema,
        )
        if tools:
            kwargs["tools"] = tools
        if not is_haiku:
            kwargs["thinking"] = {"type": "adaptive"}
            kwargs["output_config"] = {"effort": effort}
            kwargs["fallbacks"] = "default"
            kwargs["betas"] = [FALLBACK_BETA]

        messages = kwargs["messages"]
        for _ in range(4):  # server tools may pause a long turn; resume it
            try:
                response = self.client.beta.messages.parse(**kwargs)
            except anthropic.BadRequestError as e:
                raise AgentError(f"{agent}: bad request: {e.message}") from e
            except (anthropic.AuthenticationError, anthropic.PermissionDeniedError) as e:
                raise AgentError(f"{agent}: Claude API key missing or not allowed: {e.message}") from e
            except anthropic.RateLimitError as e:
                raise AgentError(f"{agent}: rate limited, retry later") from e
            except anthropic.APIStatusError as e:
                raise AgentError(f"{agent}: API error {e.status_code}: {e.message}") from e
            except anthropic.APIConnectionError as e:
                raise AgentError(f"{agent}: network error reaching the Claude API") from e
            if response.stop_reason != "pause_turn":
                break
            messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "refusal":
            detail = getattr(response.stop_details, "explanation", "") if response.stop_details else ""
            raise AgentError(f"{agent}: model declined the request. {detail}".strip())
        if response.stop_reason == "max_tokens":
            raise AgentError(f"{agent}: output was cut off at max_tokens")
        parsed = response.parsed_output
        if parsed is None:
            raise AgentError(f"{agent}: no valid structured output")

        usage = response.usage
        log.info("%s %s in=%s cached=%s out=%s", agent, response.model, usage.input_tokens,
                 usage.cache_read_input_tokens, usage.output_tokens)
        if self.audit:
            self.audit(agent=agent, model=response.model, brief_id=brief_id, task=task,
                       output=parsed.model_dump_json(), usage=json.dumps(
                           {"input": usage.input_tokens, "cache_read": usage.cache_read_input_tokens,
                            "cache_write": usage.cache_creation_input_tokens, "output": usage.output_tokens}))
        return parsed
