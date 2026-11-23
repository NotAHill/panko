"""Claude through the official Anthropic SDK: structured JSON output, vision, prompt caching, token counting,
Message Batches (half price) and server-side refusal fallbacks."""
from __future__ import annotations

import json

from panko.providers import register
from panko.providers.base import LLM, Answer, Ask

FALLBACK_BETA = "server-side-fallback-2026-07-01"


@register("llm", "anthropic")
class Claude(LLM):
    needs = ("ANTHROPIC_API_KEY",)

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.model = cfg.get("model", "claude-opus-5-5")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            import os

            import anthropic
            # an empty ANTHROPIC_BASE_URL in the environment would otherwise override the default endpoint
            base = os.environ.get("ANTHROPIC_BASE_URL") or self.cfg.get("base_url") or "https://api.anthropic.com"
            self._client = anthropic.Anthropic(max_retries=5, base_url=base)
        return self._client

    # request building ------------------------------------------------------------------------------------------

    def _content(self, parts: list) -> list[dict]:
        from panko.providers.llm import b64
        out = []
        for p in parts:
            if isinstance(p, str):
                out.append({"type": "text", "text": p})
            elif "image" in p:
                mt, data = b64(p["image"])
                out.append({"type": "image", "source": {"type": "base64", "media_type": mt, "data": data}})
            elif "pdf" in p:
                _, data = b64(p["pdf"])
                out.append({"type": "document", "source": {"type": "base64", "media_type": "application/pdf", "data": data}})
            else:
                raise ValueError(f"unknown part {list(p)}")
        return out

    def params(self, a: Ask) -> dict:
        """The Messages API body for one request (shared by `ask`, `count_tokens` and batches)."""
        body = {"model": self.model, "max_tokens": a.max_tokens,
                # the task prompt is identical across a run's items, so it's cached after the first request
                "system": [{"type": "text", "text": a.system, "cache_control": {"type": "ephemeral"}}],
                "messages": [{"role": "user", "content": self._content(a.parts)}]}
        oc = {}
        effort = a.effort or self.cfg.get("effort")
        if effort:
            oc["effort"] = effort
        if a.schema:
            oc["format"] = {"type": "json_schema", "schema": a.schema}
        if oc:
            body["output_config"] = oc
        return body

    # answers ---------------------------------------------------------------------------------------------------

    def _answer(self, a_id: str, msg, batch: bool = False) -> Answer:
        from panko.providers.llm import cost
        u = msg.usage
        usage = {"input": u.input_tokens, "output": u.output_tokens,
                 "cache_read": getattr(u, "cache_read_input_tokens", 0) or 0,
                 "cache_write": getattr(u, "cache_creation_input_tokens", 0) or 0}
        ans = Answer(id=a_id, model=msg.model, usage=usage, cost=cost(msg.model, usage, batch), batch=batch)
        if msg.stop_reason == "refusal":
            cat = getattr(msg.stop_details, "category", None) if msg.stop_details else None
            ans.error = f"refused ({cat})" if cat else "refused"
            return ans
        if msg.stop_reason == "max_tokens":
            ans.error = "cut off at max_tokens: raise max_tokens or split the input"
            return ans
        text = "".join(b.text for b in msg.content if b.type == "text")
        try:
            ans.data = json.loads(text) if text.lstrip().startswith(("{", "[")) else text
        except json.JSONDecodeError as e:
            ans.error = f"bad JSON: {e}"
        return ans

    def ask(self, a: Ask) -> Answer:
        import anthropic

        from panko.providers.llm import OutOfCredits
        body = self.params(a)
        if self.cfg.get("fallbacks", True):   # on a policy decline the API re-runs the request on a fallback model
            body |= {"betas": [FALLBACK_BETA], "fallbacks": "default"}
        try:
            if a.max_tokens > 16000:              # long outputs stream, so the HTTP request can't time out
                with self.client.beta.messages.stream(**body) as s:
                    msg = s.get_final_message()
            else:
                msg = self.client.beta.messages.create(**body)
        except anthropic.BadRequestError as e:
            if "credit balance" in str(e).lower():
                raise OutOfCredits("Anthropic: credit balance too low; add credits, then re-run") from e
            return Answer(id=a.id, model=self.model, error=f"bad request: {e.message}")
        except anthropic.APIStatusError as e:
            return Answer(id=a.id, model=self.model, error=f"API error {e.status_code}: {e.message}")
        except anthropic.APIConnectionError as e:
            return Answer(id=a.id, model=self.model, error=f"connection error: {e}")
        return self._answer(a.id, msg)

    def count_tokens(self, a: Ask) -> int | None:
        body = self.params(a)
        body.pop("max_tokens")
        return self.client.messages.count_tokens(**body).input_tokens

    # Message Batches ---------------------------------------------------------------------------------------------

    def batch_submit(self, asks: list[Ask]) -> str:
        from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
        from anthropic.types.messages.batch_create_params import Request
        reqs = [Request(custom_id=a.id, params=MessageCreateParamsNonStreaming(**self.params(a))) for a in asks]
        return self.client.messages.batches.create(requests=reqs).id

    def batch_status(self, batch_id: str) -> dict:
        b = self.client.messages.batches.retrieve(batch_id)
        c = b.request_counts
        return {"done": b.processing_status == "ended", "status": b.processing_status,
                "counts": {"processing": c.processing, "succeeded": c.succeeded, "errored": c.errored,
                           "canceled": c.canceled, "expired": c.expired}}

    def batch_results(self, batch_id: str) -> list[Answer]:
        out = []
        for r in self.client.messages.batches.results(batch_id):   # any order: keyed by custom_id
            if r.result.type == "succeeded":
                out.append(self._answer(r.custom_id, r.result.message, batch=True))
            else:
                err = getattr(getattr(r.result, "error", None), "type", "") or r.result.type
                out.append(Answer(id=r.custom_id, model=self.model, error=f"batch {r.result.type}: {err}", batch=True))
        return out
