"""akousma — Python reference implementation of the Sonic Field akousma protocol.

An *akousma* is one sound's memory record (audio + provenance + listening + lineage);
the *akousmata* is the shared cross-app store. This package is consumed by oída, germ,
and algophony so they read/write one shared memory layer with one lineage model.

See earworm/docs/akousma_spec_v1.md and earworm/docs/akousmata-store.md.
"""
from __future__ import annotations

import json
import os
import secrets
import sqlite3
import time
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1.0.0"
_SCHEMA_PATH = Path(__file__).with_name("akousma.schema.json")

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"


def _b32(n: int, length: int) -> str:
    out = []
    for _ in range(length):
        out.append(_CROCKFORD[n & 0x1F])
        n >>= 5
    return "".join(reversed(out))


def new_id(prefix: str = "akm") -> str:
    """ULID-style sortable id: 48-bit ms timestamp + 80-bit randomness, Crockford base32."""
    ms = int(time.time() * 1000)
    rand = secrets.randbits(80)
    return f"{prefix}_{_b32(ms, 10)}{_b32(rand, 16)}"


# ---------------------------------------------------------------------------
# schema / validation
# ---------------------------------------------------------------------------

def load_schema() -> dict[str, Any]:
    return json.loads(_SCHEMA_PATH.read_text())


def validation_errors(record: dict[str, Any]) -> list[str]:
    """Return human-readable validation errors ([] if valid). Uses jsonschema if
    available, else a minimal built-in check of required blocks."""
    try:
        from jsonschema import Draft7Validator

        validator = Draft7Validator(load_schema())
        return [
            f"{'/'.join(str(p) for p in e.path) or '<root>'}: {e.message}"
            for e in sorted(validator.iter_errors(record), key=lambda e: list(e.path))
        ]
    except ModuleNotFoundError:
        errors: list[str] = []
        for key in ("akousma_id", "schema_version", "created_at", "audio", "provenance", "lineage"):
            if key not in record:
                errors.append(f"<root>: '{key}' is required")
        if isinstance(record.get("audio"), dict) and "asset_id" not in record["audio"]:
            errors.append("audio: 'asset_id' is required")
        if isinstance(record.get("lineage"), dict) and "parent_akousma_ids" not in record["lineage"]:
            errors.append("lineage: 'parent_akousma_ids' is required")
        return errors


def is_valid(record: dict[str, Any]) -> bool:
    return not validation_errors(record)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_akousma(
    *,
    audio: dict[str, Any],
    originating_app: str,
    source_type: str = "recorded",
    origin: str = "file",
    listening: dict[str, Any] | None = None,
    parent_akousma_ids: Iterable[str] | None = None,
    operation: str | None = None,
    prompt: str | None = None,
    model: str | None = None,
    params: dict[str, Any] | None = None,
    tags: Iterable[str] | None = None,
    extensions: dict[str, Any] | None = None,
    session_id: str | None = None,
) -> dict[str, Any]:
    """Build a valid akousma record. ``audio`` must at least contain ``asset_id``."""
    lineage: dict[str, Any] = {"parent_akousma_ids": list(parent_akousma_ids or [])}
    for k, v in (("operation", operation), ("prompt", prompt), ("model", model)):
        if v is not None:
            lineage[k] = v
    if params:
        lineage["params"] = params
    record: dict[str, Any] = {
        "akousma_id": new_id(),
        "schema_version": SCHEMA_VERSION,
        "created_at": _utc_now(),
        "audio": audio,
        "provenance": {
            "source_type": source_type,
            "origin": origin,
            "originating_app": originating_app,
            "created_at": _utc_now(),
        },
        "listening": listening or {},
        "lineage": lineage,
        "tags": list(tags or []),
        "annotations": {},
        "extensions": extensions or {},
    }
    if session_id:
        record["session_id"] = session_id
    return record


# ---------------------------------------------------------------------------
# the shared akousmata store
# ---------------------------------------------------------------------------

def default_store_path() -> Path:
    env = os.getenv("AKOUSMATA_PATH")
    if env:
        return Path(env).expanduser()
    return Path.home() / "Documents" / "SFL" / "akousmata"


class AkousmataStore:
    """SQLite-indexed, content-addressed shared store for akousma records."""

    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root).expanduser() if root else default_store_path()
        self.objects_dir = self.root / "objects"
        self.objects_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.root / "index.sqlite"
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_db()

    def _init_db(self) -> None:
        self.conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS akousmata (
              akousma_id      TEXT PRIMARY KEY,
              created_at      TEXT NOT NULL,
              originating_app TEXT,
              source_type     TEXT,
              origin          TEXT,
              content_hash    TEXT,
              session_id      TEXT,
              record          TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS lineage_edges (
              child_id  TEXT NOT NULL,
              parent_id TEXT NOT NULL,
              PRIMARY KEY (child_id, parent_id)
            );
            CREATE INDEX IF NOT EXISTS idx_lineage_parent ON lineage_edges(parent_id);
            """
        )
        self.conn.commit()

    # --- content-addressed audio -----------------------------------------
    def put_audio(self, data: bytes, ext: str = "wav") -> str:
        digest = sha256(data).hexdigest()
        shard = self.objects_dir / digest[:2]
        shard.mkdir(parents=True, exist_ok=True)
        dest = shard / f"{digest}.{ext}"
        if not dest.exists():
            dest.write_bytes(data)
        return f"akousmata://objects/{digest}.{ext}"

    def resolve_uri(self, uri: str) -> Path | None:
        prefix = "akousmata://objects/"
        if not uri.startswith(prefix):
            return None
        name = uri[len(prefix):]
        digest = name.split(".")[0]
        return self.objects_dir / digest[:2] / name

    # --- records ----------------------------------------------------------
    def put(self, record: dict[str, Any]) -> str:
        errors = validation_errors(record)
        if errors:
            raise ValueError("invalid akousma:\n" + "\n".join(errors))
        rid = record["akousma_id"]
        self.conn.execute(
            """INSERT OR REPLACE INTO akousmata
               (akousma_id, created_at, originating_app, source_type, origin, content_hash, session_id, record)
               VALUES (?,?,?,?,?,?,?,?)""",
            (
                rid,
                record["created_at"],
                record["provenance"].get("originating_app"),
                record["provenance"].get("source_type"),
                record["provenance"].get("origin"),
                record.get("audio", {}).get("content_hash"),
                record.get("session_id"),
                json.dumps(record),
            ),
        )
        self.conn.execute("DELETE FROM lineage_edges WHERE child_id=?", (rid,))
        for parent in record.get("lineage", {}).get("parent_akousma_ids", []):
            self.conn.execute(
                "INSERT OR IGNORE INTO lineage_edges (child_id, parent_id) VALUES (?,?)",
                (rid, parent),
            )
        self.conn.commit()
        return rid

    def get(self, akousma_id: str) -> dict[str, Any] | None:
        row = self.conn.execute(
            "SELECT record FROM akousmata WHERE akousma_id=?", (akousma_id,)
        ).fetchone()
        return json.loads(row["record"]) if row else None

    def query(
        self,
        *,
        originating_app: str | None = None,
        source_type: str | None = None,
        origin: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses, args = [], []
        for col, val in (("originating_app", originating_app), ("source_type", source_type), ("origin", origin)):
            if val is not None:
                clauses.append(f"{col}=?")
                args.append(val)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        args.append(limit)
        rows = self.conn.execute(
            f"SELECT record FROM akousmata {where} ORDER BY created_at DESC LIMIT ?", args
        ).fetchall()
        return [json.loads(r["record"]) for r in rows]

    def parents(self, akousma_id: str) -> list[str]:
        return [
            r["parent_id"]
            for r in self.conn.execute(
                "SELECT parent_id FROM lineage_edges WHERE child_id=?", (akousma_id,)
            ).fetchall()
        ]

    def children(self, akousma_id: str) -> list[str]:
        return [
            r["child_id"]
            for r in self.conn.execute(
                "SELECT child_id FROM lineage_edges WHERE parent_id=?", (akousma_id,)
            ).fetchall()
        ]

    def ancestors(self, akousma_id: str) -> list[str]:
        seen, stack, out = {akousma_id}, list(self.parents(akousma_id)), []
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            out.append(cur)
            stack.extend(self.parents(cur))
        return out

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "AkousmataStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


__all__ = [
    "SCHEMA_VERSION",
    "new_id",
    "load_schema",
    "validation_errors",
    "is_valid",
    "new_akousma",
    "default_store_path",
    "AkousmataStore",
]
