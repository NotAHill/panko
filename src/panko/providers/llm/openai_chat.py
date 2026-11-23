"""OpenAI chat models as an alternative to Claude (plain HTTP, like the image provider). Set `[llm.openai] model`
and its price in `[llm.prices]` to use it. Batches aren't wired for it yet."""
from __future__ import annotations

import json
import time

import httpx

from panko.config import secret
from panko.providers import register
from panko.providers.base import LLM, Answer, Ask

API = "https://api.openai.com/v1"


@register("llm", "openai")
class OpenAIChat(LLM):
    needs = ("OPENAI_API_KEY",)

    def __init__(self, cfg: dict):
        super().__init__(cfg)
        self.model = cfg.get("model", "")

    def ready(self) -> bool:
        return bool(self.model) and super().ready()

    def body(self, a: Ask) -> dict:
        from panko.providers.llm import b64
        content = []
        for p in a.parts:
            if isinstance(p, str):
                content.append({"type": "text", "text": p})
            elif "image" in p:
                mt, data = b64(p["image"])
                content.append({"type": "image_url", "image_url": {"url": f"data:{mt};base64,{data}"}})
            elif "pdf" in p:
                _, data = b64(p["pdf"])
                content.append({"type": "file", "file": {"filename": "doc.pdf", "file_data": f"data:application/pdf;base64,{data}"}})
        body = {"model": self.model, "max_completion_tokens": a.max_tokens,
                "messages": [{"role": "system", "content": a.system}, {"role": "user", "content": content}]}
        if a.effort or self.cfg.get("effort"):
            body["reasoning_effort"] = {"xhigh": "high", "max": "high"}.get(a.effort, a.effort) or self.cfg["effort"]
        if a.schema:
            body["response_format"] = {"type": "json_schema", "json_schema": {"name": "answer", "schema": a.schema, "strict": True}}
        return body

    def ask(self, a: Ask) -> Answer:
        from panko.providers.llm import OutOfCredits, cost
        for attempt in range(5):
            r = httpx.post(f"{API}/chat/completions", json=self.body(a), timeout=600,
                           headers={"Authorization": f"Bearer {secret('OPENAI_API_KEY')}"})
            if r.status_code == 429 and "insufficient_quota" in r.text:
                raise OutOfCredits("OpenAI: no credits left; add credits, then re-run")
            if r.status_code not in (429, 500, 502, 503, 504):
                break
            time.sleep(5 * (attempt + 1))
        if r.status_code != 200:
            return Answer(id=a.id, model=self.model, error=f"API error {r.status_code}: {r.text[:300]}")
        j = r.json()
        u = j.get("usage", {})
        cached = (u.get("prompt_tokens_details") or {}).get("cached_tokens", 0)
        usage = {"input": u.get("prompt_tokens", 0) - cached, "output": u.get("completion_tokens", 0), "cache_read": cached}
        ans = Answer(id=a.id, model=j.get("model", self.model), usage=usage, cost=cost(self.model, usage))
        choice = j["choices"][0]
        if choice.get("finish_reason") == "length":
            ans.error = "cut off at max_tokens: raise max_tokens or split the input"
            return ans
        if choice["message"].get("refusal"):
            ans.error = f"refused: {choice['message']['refusal'][:200]}"
            return ans
        text = choice["message"].get("content") or ""
        try:
            ans.data = json.loads(text) if a.schema else text
        except json.JSONDecodeError as e:
            ans.error = f"bad JSON: {e}"
        return ans
