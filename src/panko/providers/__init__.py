"""Provider registry. Each capability (audio, images, ...) has a chain of named
providers set in config/panko.toml; `chain("audio")` returns them in order,
skipping any that aren't configured (e.g. missing API key)."""
from __future__ import annotations

from panko.config import settings
from panko.providers.base import Provider

_REGISTRY: dict[str, dict[str, type[Provider]]] = {}


def register(capability: str, name: str):
    def deco(cls):
        _REGISTRY.setdefault(capability, {})[name] = cls
        cls.name = name
        return cls
    return deco


def available(capability: str) -> list[str]:
    _load_all()
    return sorted(_REGISTRY.get(capability, {}))


def chain(capability: str) -> list[Provider]:
    _load_all()
    cfg = settings().get(capability, {})
    out = []
    for name in cfg.get("chain", []):
        cls = _REGISTRY.get(capability, {}).get(name)
        if cls is None:
            raise KeyError(f"unknown {capability} provider '{name}' (known: {available(capability)})")
        p = cls(cfg.get(name, {}))
        if p.ready():
            out.append(p)
    return out


def _load_all():
    # importing the modules runs their @register decorators
    from panko.providers import imagegen, images, llm, tts  # noqa: F401
