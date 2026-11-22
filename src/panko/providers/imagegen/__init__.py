"""Image generation, used only when no real picture is found.
'generate' in the images chain delegates to whichever backend [images.generate].provider names."""
from __future__ import annotations

import base64

import httpx

from panko.config import secret, settings
from panko.providers import register
from panko.providers.base import Image, ImageGen

BACKENDS = {"openai": "OPENAI_API_KEY", "recraft": "RECRAFT_API_KEY", "gemini": "GEMINI_API_KEY"}


@register("images", "generate")
class Generate(ImageGen):
    @property
    def backend(self):
        return settings()["images"].get("generate", {}).get("provider", "openai")

    def ready(self):
        return bool(secret(BACKENDS.get(self.backend, "")))

    def generate(self, prompt, out):
        cfg = settings()["images"]["generate"]
        full = f"{prompt}. {cfg.get('style', '')}"
        if self.backend == "openai":
            r = httpx.post("https://api.openai.com/v1/images/generations", timeout=180,
                           headers={"Authorization": f"Bearer {secret('OPENAI_API_KEY')}"},
                           json={"model": cfg.get("model", "gpt-image-1"), "prompt": full, "size": "1024x1024"})
            r.raise_for_status()
            out.write_bytes(base64.b64decode(r.json()["data"][0]["b64_json"]))
            return Image(path=out, source=f"Generated ({cfg.get('model')})", generated=True, meta={"prompt": full})
        raise NotImplementedError(f"image backend '{self.backend}' not wired yet")
