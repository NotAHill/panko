"""Image generation, used only when no real picture is found.
'generate' in the images chain delegates to whichever backend [images.generate].provider names."""
from __future__ import annotations

import base64
import json
import time

import httpx

from panko.config import secret, settings
from panko.providers import register
from panko.providers.base import Image, ImageGen


class OutOfCredits(RuntimeError):
    pass


BACKENDS = {"openai": "OPENAI_API_KEY", "recraft": "RECRAFT_API_KEY", "gemini": "GEMINI_API_KEY"}


@register("images", "generate")
class Generate(ImageGen):
    @property
    def backend(self):
        return settings()["images"].get("generate", {}).get("provider", "openai")

    def ready(self):
        return bool(secret(BACKENDS.get(self.backend, "")))

    @staticmethod
    def body(prompt: str) -> dict:
        """The request body for one picture: the scene prompt plus the house style from config."""
        cfg = settings()["images"]["generate"]
        return {"model": cfg.get("model", "gpt-image-2"), "prompt": f"{prompt}. {cfg.get('style', '')}",
                "size": cfg.get("size", "1024x1024"), "quality": cfg.get("quality", "low")}

    def generate(self, prompt, out):
        cfg = settings()["images"]["generate"]
        if self.backend == "openai":
            body = self.body(prompt)
            full = body["prompt"]
            for attempt in range(5):
                r = httpx.post(f"{API}/images/generations", timeout=300, headers=_auth(), json=body)
                if r.status_code == 429 and "insufficient_quota" in r.text:
                    raise OutOfCredits("OpenAI: no credits left; add credits, then re-run")
                if r.status_code not in (429, 500, 502, 503):
                    break
                time.sleep(10 * (attempt + 1))
            r.raise_for_status()
            out.write_bytes(base64.b64decode(r.json()["data"][0]["b64_json"]))
            return Image(path=out, source=f"Generated ({cfg.get('model')})", generated=True, meta={"prompt": full})
        raise NotImplementedError(f"image backend '{self.backend}' not wired yet")

    # OpenAI Batch API: half the price, no rate limit, results within 24 hours.
    def batch_submit(self, prompts: dict[str, str]) -> str:
        """Submit {custom id: scene prompt} as one batch; returns the batch id."""
        if self.backend != "openai":
            raise NotImplementedError(f"batch drawing not wired for '{self.backend}'")
        lines = [json.dumps({"custom_id": k, "method": "POST", "url": "/v1/images/generations", "body": self.body(p)},
                            ensure_ascii=False) for k, p in prompts.items()]
        f = httpx.post(f"{API}/files", headers=_auth(), timeout=300, data={"purpose": "batch"},
                       files={"file": ("panko-draw.jsonl", "\n".join(lines).encode(), "application/jsonl")})
        _check(f)
        b = httpx.post(f"{API}/batches", headers=_auth(), timeout=60, json={
            "input_file_id": f.json()["id"], "endpoint": "/v1/images/generations", "completion_window": "24h"})
        _check(b)
        return b.json()["id"]

    def batch_status(self, batch_id: str) -> dict:
        r = httpx.get(f"{API}/batches/{batch_id}", headers=_auth(), timeout=60)
        _check(r)
        return r.json()

    def batch_results(self, batch: dict) -> dict[str, bytes | str]:
        """{custom id: PNG bytes, or an error message} for a finished batch."""
        res: dict[str, bytes | str] = {}
        for key in ("output_file_id", "error_file_id"):
            if not batch.get(key):
                continue
            r = httpx.get(f"{API}/files/{batch[key]}/content", headers=_auth(), timeout=600)
            _check(r)
            for line in r.text.splitlines():
                if not line.strip():
                    continue
                x = json.loads(line)
                resp = x.get("response") or {}
                if resp.get("status_code") == 200:
                    res[x["custom_id"]] = base64.b64decode(resp["body"]["data"][0]["b64_json"])
                else:
                    err = x.get("error") or (resp.get("body") or {}).get("error") or {}
                    res[x["custom_id"]] = f"error: {err.get('message', err) or resp.get('status_code')}"
        return res


API = "https://api.openai.com/v1"


def _auth() -> dict:
    return {"Authorization": f"Bearer {secret('OPENAI_API_KEY')}"}


def _check(r: httpx.Response):
    if r.status_code == 429 and "insufficient_quota" in r.text:
        raise OutOfCredits("OpenAI: no credits left; add credits, then re-run")
    if r.status_code >= 400:
        raise httpx.HTTPStatusError(f"{r.status_code}: {r.text[:300]}", request=r.request, response=r)
