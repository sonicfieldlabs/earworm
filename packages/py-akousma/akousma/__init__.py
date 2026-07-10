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

SCHEMA_VERSION = "1.1.0"
_SCHEMA_PATH = Path(__file__).with_name("akousma.schema.json")

RELATION_TYPES = (
    "variant_of",
    "response_to",
    "same_source_as",
    "recurrence_of",
    "series_with",
    "compares_with",
    "replaces",
    "other",
)

PIPELINE_EFFECTS = (
    "capture",
    "telephony",
    "acousmatization",
    "amplification",
    "phonofixation",
    "phonogeneration",
    "reshaping",
)

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
    relations: Iterable[dict[str, Any]] | None = None,
    tags: Iterable[str] | None = None,
    extensions: dict[str, Any] | None = None,
    session_id: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    """Build a valid akousma record. ``audio`` must at least contain ``asset_id``."""
    lineage: dict[str, Any] = {"parent_akousma_ids": list(parent_akousma_ids or [])}
    for k, v in (("operation", operation), ("prompt", prompt), ("model", model)):
        if v is not None:
            lineage[k] = v
    if params:
        lineage["params"] = params
    if relations:
        lineage["relations"] = [dict(rel) for rel in relations]
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
    if summary:
        record["summary"] = summary
    return record


def relation(rel_type: str, target_akousma_id: str, note: str | None = None) -> dict[str, Any]:
    """Build a typed lineage relation (kinship link, not causal parenthood)."""
    if rel_type not in RELATION_TYPES:
        raise ValueError(f"unknown relation type: {rel_type}. Valid types: {', '.join(RELATION_TYPES)}")
    rel: dict[str, Any] = {"type": rel_type, "target_akousma_id": target_akousma_id}
    if note:
        rel["note"] = note
    return rel


def add_listening(
    record: dict[str, Any],
    namespace: str,
    payload: dict[str, Any],
    *,
    contract: str | None = None,
    summary: str | None = None,
) -> dict[str, Any]:
    """Attach a producer's listening entry under its namespace using the v1.1
    envelope: ``{contract?, created_at, summary?, payload}``. Additive: never
    reshapes another producer's block."""
    entry: dict[str, Any] = {"created_at": _utc_now(), "payload": payload}
    if contract:
        entry["contract"] = contract
    if summary:
        entry["summary"] = summary
    record.setdefault("listening", {})[namespace] = entry
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
            CREATE TABLE IF NOT EXISTS relation_edges (
              from_id  TEXT NOT NULL,
              rel_type TEXT NOT NULL,
              to_id    TEXT NOT NULL,
              PRIMARY KEY (from_id, rel_type, to_id)
            );
            CREATE INDEX IF NOT EXISTS idx_relation_to ON relation_edges(to_id);
            CREATE INDEX IF NOT EXISTS idx_akousmata_hash ON akousmata(content_hash);
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
        self.conn.execute("DELETE FROM relation_edges WHERE from_id=?", (rid,))
        for rel in record.get("lineage", {}).get("relations", []) or []:
            self.conn.execute(
                "INSERT OR IGNORE INTO relation_edges (from_id, rel_type, to_id) VALUES (?,?,?)",
                (rid, rel.get("type", "other"), rel.get("target_akousma_id", "")),
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
        session_id: str | None = None,
        content_hash: str | None = None,
        tag: str | None = None,
        text: str | None = None,
        since: str | None = None,
        until: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses, args = [], []
        for col, val in (
            ("originating_app", originating_app),
            ("source_type", source_type),
            ("origin", origin),
            ("session_id", session_id),
            ("content_hash", content_hash),
        ):
            if val is not None:
                clauses.append(f"{col}=?")
                args.append(val)
        if since is not None:
            clauses.append("created_at>=?")
            args.append(since)
        if until is not None:
            clauses.append("created_at<=?")
            args.append(until)
        if tag is not None:
            # tags live inside the record JSON; the quoted-string LIKE is a
            # superset pre-filter, exact tag membership is enforced post-query
            clauses.append("record LIKE ?")
            args.append(f'%{json.dumps(tag)}%')
        if text is not None:
            clauses.append("record LIKE ?")
            args.append(f"%{text}%")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        args.append(limit)
        rows = self.conn.execute(
            f"SELECT record FROM akousmata {where} ORDER BY created_at DESC LIMIT ?", args
        ).fetchall()
        records = [json.loads(r["record"]) for r in rows]
        if tag is not None:
            records = [record for record in records if tag in (record.get("tags") or [])]
        return records

    def find_by_hash(self, content_hash: str) -> list[dict[str, Any]]:
        """All records carrying this audio content hash (dedupe / recurrence lookup)."""
        return self.query(content_hash=content_hash, limit=1000)

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

    def descendants(self, akousma_id: str) -> list[str]:
        seen, stack, out = {akousma_id}, list(self.children(akousma_id)), []
        while stack:
            cur = stack.pop()
            if cur in seen:
                continue
            seen.add(cur)
            out.append(cur)
            stack.extend(self.children(cur))
        return out

    # --- typed relations (kinship, not parenthood) -------------------------
    def relations(self, akousma_id: str) -> list[dict[str, str]]:
        """Outgoing typed relations of a record."""
        return [
            {"type": r["rel_type"], "target_akousma_id": r["to_id"]}
            for r in self.conn.execute(
                "SELECT rel_type, to_id FROM relation_edges WHERE from_id=?", (akousma_id,)
            ).fetchall()
        ]

    def related(self, akousma_id: str, rel_type: str | None = None) -> list[dict[str, str]]:
        """All records connected to this one through typed relations, both
        directions. Incoming links are reported with direction 'incoming'."""
        clause, args = "", [akousma_id, akousma_id]
        if rel_type is not None:
            clause = " AND rel_type=?"
            args.append(rel_type)
        rows = self.conn.execute(
            f"SELECT from_id, rel_type, to_id FROM relation_edges WHERE (from_id=? OR to_id=?){clause}",
            args,
        ).fetchall()
        out = []
        for r in rows:
            if r["from_id"] == akousma_id:
                out.append({"type": r["rel_type"], "akousma_id": r["to_id"], "direction": "outgoing"})
            else:
                out.append({"type": r["rel_type"], "akousma_id": r["from_id"], "direction": "incoming"})
        return out

    # --- library operations (akousmata navigator surface) -------------------
    def tags(self) -> list[dict[str, Any]]:
        """Distinct tags with usage counts, most used first."""
        counts: dict[str, int] = {}
        for row in self.conn.execute("SELECT record FROM akousmata").fetchall():
            for tag in json.loads(row["record"]).get("tags") or []:
                counts[str(tag)] = counts.get(str(tag), 0) + 1
        return [
            {"tag": tag, "count": count}
            for tag, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ]

    def changed_since(
        self,
        iso_timestamp: str,
        *,
        limit: int = 200,
        after_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """Records after a durable watcher cursor.

        ``after_id`` disambiguates records sharing the same timestamp, so a
        bounded batch cannot skip siblings when more than ``limit`` records
        were captured within one clock tick. Existing callers that omit it
        retain the original strictly-after timestamp behavior.
        """
        if after_id is None:
            rows = self.conn.execute(
                "SELECT record FROM akousmata WHERE created_at>? ORDER BY created_at ASC, akousma_id ASC LIMIT ?",
                (iso_timestamp, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT record FROM akousmata
                   WHERE created_at>? OR (created_at=? AND akousma_id>?)
                   ORDER BY created_at ASC, akousma_id ASC LIMIT ?""",
                (iso_timestamp, iso_timestamp, after_id, limit),
            ).fetchall()
        return [json.loads(r["record"]) for r in rows]

    def forget(self, akousma_id: str, *, delete_audio: bool = False) -> bool:
        """The memory operation 'forget': remove one record and its edges.

        With ``delete_audio`` the content-addressed object is also removed —
        but only when no other record references the same content hash.
        Returns False when the record does not exist. Edges pointing AT the
        forgotten record are kept: absence is information, and ``verify()``
        will report them as dangling rather than erasing the trace."""
        record = self.get(akousma_id)
        if record is None:
            return False
        if delete_audio:
            content_hash = str(record.get("audio", {}).get("content_hash") or "")
            uri = str(record.get("audio", {}).get("uri") or "")
            others = [
                r for r in self.conn.execute(
                    "SELECT akousma_id FROM akousmata WHERE content_hash=? AND akousma_id<>?",
                    (content_hash, akousma_id),
                ).fetchall()
            ] if content_hash else [True]
            if uri.startswith("akousmata://objects/") and not others:
                path = self.resolve_uri(uri)
                if path is not None and path.exists():
                    path.unlink()
        self.conn.execute("DELETE FROM akousmata WHERE akousma_id=?", (akousma_id,))
        self.conn.execute("DELETE FROM lineage_edges WHERE child_id=?", (akousma_id,))
        self.conn.execute("DELETE FROM relation_edges WHERE from_id=?", (akousma_id,))
        self.conn.commit()
        return True

    # --- maintenance --------------------------------------------------------
    def reindex(self) -> int:
        """Rebuild lineage and relation edges from the stored records (e.g. after
        upgrading a store created before relations existed). Returns record count."""
        rows = self.conn.execute("SELECT record FROM akousmata").fetchall()
        self.conn.execute("DELETE FROM lineage_edges")
        self.conn.execute("DELETE FROM relation_edges")
        for row in rows:
            record = json.loads(row["record"])
            rid = record["akousma_id"]
            for parent in record.get("lineage", {}).get("parent_akousma_ids", []):
                self.conn.execute(
                    "INSERT OR IGNORE INTO lineage_edges (child_id, parent_id) VALUES (?,?)",
                    (rid, parent),
                )
            for rel in record.get("lineage", {}).get("relations", []) or []:
                self.conn.execute(
                    "INSERT OR IGNORE INTO relation_edges (from_id, rel_type, to_id) VALUES (?,?,?)",
                    (rid, rel.get("type", "other"), rel.get("target_akousma_id", "")),
                )
        self.conn.commit()
        return len(rows)

    def verify(self) -> dict[str, list[str]]:
        """Integrity report — the archive of absence. Dangling links and missing
        audio are reported, never silently discarded: a dead record is still
        lineage information."""
        report: dict[str, list[str]] = {
            "dangling_parents": [],
            "dangling_relations": [],
            "missing_audio": [],
            "invalid_records": [],
        }
        ids = {r["akousma_id"] for r in self.conn.execute("SELECT akousma_id FROM akousmata").fetchall()}
        for row in self.conn.execute("SELECT record FROM akousmata").fetchall():
            record = json.loads(row["record"])
            rid = record["akousma_id"]
            errors = validation_errors(record)
            if errors:
                report["invalid_records"].append(f"{rid}: {errors[0]}")
            for parent in record.get("lineage", {}).get("parent_akousma_ids", []):
                if parent not in ids:
                    report["dangling_parents"].append(f"{rid} -> {parent}")
            for rel in record.get("lineage", {}).get("relations", []) or []:
                target = rel.get("target_akousma_id", "")
                if target not in ids:
                    report["dangling_relations"].append(f"{rid} -[{rel.get('type', 'other')}]-> {target}")
            uri = record.get("audio", {}).get("uri", "")
            if uri.startswith("akousmata://objects/"):
                path = self.resolve_uri(uri)
                if path is not None and not path.exists():
                    report["missing_audio"].append(f"{rid}: {uri}")
        return report

    def close(self) -> None:
        self.conn.close()

    def __enter__(self) -> "AkousmataStore":
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()


__all__ = [
    "SCHEMA_VERSION",
    "RELATION_TYPES",
    "PIPELINE_EFFECTS",
    "new_id",
    "load_schema",
    "validation_errors",
    "is_valid",
    "new_akousma",
    "relation",
    "add_listening",
    "default_store_path",
    "AkousmataStore",
]
