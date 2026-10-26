"""CTranslate2 settings shared by the speech and translation models."""

from __future__ import annotations

from functools import lru_cache


@lru_cache(maxsize=1)
def cpu_compute_type() -> str:
    """int8 everywhere it is supported (x86 and ARM, incl. Apple Silicon); otherwise CTranslate2's default."""
    import ctranslate2

    return "int8" if "int8" in ctranslate2.get_supported_compute_types("cpu") else "default"
