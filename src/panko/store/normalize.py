"""Matching keys ("is this word already in Panko?"), for any language: see `panko.lang`.
Display text is never normalised; only the lookup key is."""
from __future__ import annotations

from panko.lang import bare, strip_article

__all__ = ["bare", "strip_article"]
