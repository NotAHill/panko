"""Language-model providers (extraction, checking, examples, picture decisions). `[llm] chain` picks the order."""
from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from panko.config import settings


class OutOfCredits(RuntimeError):
    """The account can't pay for more requests: stop the run instead of failing every item."""


def price(model: str) -> dict | None:
    """USD per million tokens {input, output, cache_read, cache_write} from `[llm.prices]`, or None if unknown."""
    p = settings().get("llm", {}).get("prices", {}).get(model)
    if not p:
        return None
    keys = ("input", "output", "cache_read", "cache_write")
    return dict(zip(keys, p, strict=False)) if isinstance(p, list) else p


def cost(model: str, usage: dict, batch: bool = False) -> float:
    p = price(model)
    if not p:
        return 0.0
    usd = sum(usage.get(k, 0) * p.get(k, 0) for k in ("input", "output", "cache_read", "cache_write")) / 1e6
    return usd / 2 if batch else usd


def b64(path) -> tuple[str, str]:
    """(media type, base64 data) for an image or PDF file."""
    path = Path(path)
    mt = mimetypes.guess_type(path.name)[0] or ("application/pdf" if path.suffix == ".pdf" else "image/png")
    return mt, base64.standard_b64encode(path.read_bytes()).decode()


from panko.providers.llm import claude, openai_chat  # noqa: E402, F401  (registers the providers)
