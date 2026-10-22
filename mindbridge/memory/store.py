"""SQLite persistence for Operational Memory Objects (on-device, per factory)."""

from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import fields
from pathlib import Path

from mindbridge.memory.objects import MemoryObject

_COLS = [f.name for f in fields(MemoryObject) if f.name != "id"]


class MemoryStore:
    def __init__(self, path: Path | str):
        self.path = str(path)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._db.execute("PRAGMA journal_mode=WAL")
        cols = ", ".join(f"{c} TEXT" for c in _COLS)
        self._db.execute(f"CREATE TABLE IF NOT EXISTS memories (id INTEGER PRIMARY KEY AUTOINCREMENT, {cols})")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS events (id INTEGER PRIMARY KEY AUTOINCREMENT, ts REAL, type TEXT, payload TEXT)"
        )
        self._db.commit()

    # -- (de)serialisation ------------------------------------------------
    @staticmethod
    def _to_row(m: MemoryObject) -> list:
        out = []
        for c in _COLS:
            v = getattr(m, c)
            out.append(json.dumps(v) if isinstance(v, (list, dict, bool)) or v is None else v)
        return out

    @staticmethod
    def _from_row(r: sqlite3.Row) -> MemoryObject:
        kw = {}
        for f in fields(MemoryObject):
            v = r[f.name]
            if f.name == "id":
                kw["id"] = int(v)
                continue
            if f.name in ("hazards",):
                v = json.loads(v) if v else []
            elif f.name in ("needs_verification",):
                v = json.loads(v) if v else False
            elif f.name == "resolved_by":
                v = json.loads(v) if v not in (None, "null") else None
            elif f.name in ("created_at", "updated_at"):
                v = float(v)
            kw[f.name] = v
        return MemoryObject(**kw)

    # -- CRUD ---------------------------------------------------------------
    def add(self, m: MemoryObject) -> MemoryObject:
        with self._lock:
            cur = self._db.execute(
                f"INSERT INTO memories ({', '.join(_COLS)}) VALUES ({', '.join('?' * len(_COLS))})", self._to_row(m)
            )
            self._db.commit()
            m.id = int(cur.lastrowid)
        return m

    def update(self, m: MemoryObject) -> None:
        m.updated_at = time.time()
        with self._lock:
            self._db.execute(
                f"UPDATE memories SET {', '.join(f'{c}=?' for c in _COLS)} WHERE id=?", [*self._to_row(m), m.id]
            )
            self._db.commit()

    def get(self, mid: int) -> MemoryObject | None:
        with self._lock:
            r = self._db.execute("SELECT * FROM memories WHERE id=?", (mid,)).fetchone()
        return self._from_row(r) if r else None

    def all(self, limit: int = 500) -> list[MemoryObject]:
        with self._lock:
            rows = self._db.execute("SELECT * FROM memories ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [self._from_row(r) for r in rows]

    def active(self) -> list[MemoryObject]:
        return [m for m in self.all() if m.status == "active"]

    def log_event(self, type_: str, payload: dict) -> None:
        with self._lock:
            self._db.execute(
                "INSERT INTO events (ts, type, payload) VALUES (?, ?, ?)",
                (time.time(), type_, json.dumps(payload, ensure_ascii=False)),
            )
            self._db.commit()

    def clear(self) -> None:
        with self._lock:
            self._db.execute("DELETE FROM memories")
            self._db.execute("DELETE FROM events")
            self._db.commit()
