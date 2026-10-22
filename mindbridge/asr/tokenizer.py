"""Minimal Whisper detokenizer.

Reads the ``<base64-bytes> <id>`` token table shipped with the model and turns
ids back into UTF-8 text. Ids >= 50257 are special tokens and are skipped.
"""

from __future__ import annotations

import base64
from pathlib import Path

from mindbridge.languages import WHISPER_EOT


class WhisperDetokenizer:
    def __init__(self, tokens_file: Path):
        self.table: dict[int, bytes] = {}
        with open(tokens_file, encoding="utf-8") as fh:
            for line in fh:
                parts = line.rstrip("\n").split(" ")
                if len(parts) != 2:
                    continue
                tok, idx = parts
                try:
                    self.table[int(idx)] = base64.b64decode(tok)
                except ValueError:
                    continue

    def decode(self, ids: list[int]) -> str:
        raw = b"".join(self.table.get(i, b"") for i in ids if i < WHISPER_EOT)
        return raw.decode("utf-8", errors="ignore").strip()
