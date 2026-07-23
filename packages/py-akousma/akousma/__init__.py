"""akousma — Python reference implementation of the Sonic Field akousma protocol.

An *akousma* is one sound's memory record (audio + provenance + listening + lineage);
the *akousmata* is the shared cross-app store. This package is consumed by oída, germ,
and algophony so they read/write one shared memory layer with one lineage model.

See earworm/docs/akousma_spec_v1.md and earworm/docs/akousmata-store.md.
"""
from __future__ import annotations

import json
import math
import os
import secrets
import sqlite3
import sys
import time
from hashlib import sha256
from pathlib import Path
from typing import Any, Iterable

SCHEMA_VERSION = "1.4.0"
AUDITUM_CONTRACT = "earworm/auditum/v1"
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

LOCATION_SOURCES = ("gps", "network", "manual", "config", "inferred")

CAPTURE_DIRECTIONS = ("past", "future", "live")

AUDITUM_LISTENER_TYPES = ("human", "agent", "hybrid")
AUDITUM_ABSENCE_KINDS = (
    "unavailable",
    "withheld",
    "refused",
    "not_retained",
    "forgotten",
    "undetermined",
)
AUDITUM_DISAGREEMENT_STATUSES = ("preserved", "resolved", "undetermined")
AUDITUM_ACTION_STATUSES = ("proposed", "authorized", "refused", "executed", "failed", "reverted")

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
    location: dict[str, Any] | None = None,
    capture: dict[str, Any] | None = None,
    covenant: dict[str, Any] | None = None,
    auditum: dict[str, Any] | None = None,
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
    if location:
        record["location"] = dict(location)
    if capture:
        record["capture"] = dict(capture)
    if covenant:
        record["covenant"] = dict(covenant)
    if auditum:
        record["auditum"] = dict(auditum)
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


def location(
    lat: float,
    lon: float,
    *,
    accuracy_m: float | None = None,
    altitude_m: float | None = None,
    label: str | None = None,
    source: str | None = None,
    captured_at: str | None = None,
) -> dict[str, Any]:
    """Build a v1.2 location block: where the sound was heard. Optional and
    consent-scoped — attach only when the listener granted it."""
    lat = float(lat)
    lon = float(lon)
    if not -90.0 <= lat <= 90.0:
        raise ValueError(f"location: lat must be within [-90, 90], got {lat}")
    if not -180.0 <= lon <= 180.0:
        raise ValueError(f"location: lon must be within [-180, 180], got {lon}")
    if source is not None and source not in LOCATION_SOURCES:
        raise ValueError(f"location: unknown source {source!r}. Valid sources: {', '.join(LOCATION_SOURCES)}")
    loc: dict[str, Any] = {"lat": lat, "lon": lon}
    if accuracy_m is not None:
        loc["accuracy_m"] = float(accuracy_m)
    if altitude_m is not None:
        loc["altitude_m"] = float(altitude_m)
    if label:
        loc["label"] = label
    if source:
        loc["source"] = source
    loc["captured_at"] = captured_at or _utc_now()
    return loc


def capture(
    direction: str | None = None,
    *,
    seconds: float | None = None,
    trigger: str | None = None,
    armed_at: str | None = None,
    triggered_at: str | None = None,
) -> dict[str, Any]:
    """Build a v1.2 capture block: how the listening was triggered. ``past``
    slices the ring buffer that was already recording when the trigger fired;
    ``future`` records the window after it; ``live`` is an open-ended session."""
    if direction is not None and direction not in CAPTURE_DIRECTIONS:
        raise ValueError(
            f"capture: unknown direction {direction!r}. Valid directions: {', '.join(CAPTURE_DIRECTIONS)}"
        )
    cap: dict[str, Any] = {}
    if direction:
        cap["direction"] = direction
    if seconds is not None:
        if float(seconds) < 0:
            raise ValueError(f"capture: seconds must be >= 0, got {seconds}")
        cap["seconds"] = float(seconds)
    if trigger:
        cap["trigger"] = trigger
    if armed_at:
        cap["armed_at"] = armed_at
    cap["triggered_at"] = triggered_at or _utc_now()
    return cap


def covenant(
    covenant_id: str,
    *,
    name: str | None = None,
    version: str | None = None,
    contract: str | None = None,
    sha256_hex: str | None = None,
    extends: Iterable[str] | None = None,
    rules_applied: Iterable[str] | None = None,
    withheld: Iterable[dict[str, Any]] | None = None,
    commitments: int | None = None,
    note: str | None = None,
) -> dict[str, Any]:
    """Build a v1.3 covenant block: under which ethics this was listened.

    Carries the listening covenant's identity (id, hash, lineage) and its
    honest absence — what was withheld under its rules, counted and attributed,
    never described. The covenant's full text stays with its author; the
    record stays export-safe by construction."""
    covenant_id = str(covenant_id).strip()
    if not covenant_id:
        raise ValueError("covenant: id must be a non-empty string")
    if commitments is not None and int(commitments) < 0:
        raise ValueError(f"covenant: commitments must be >= 0, got {commitments}")
    block: dict[str, Any] = {"id": covenant_id}
    if name:
        block["name"] = name
    if version:
        block["version"] = version
    if contract:
        block["contract"] = contract
    if sha256_hex:
        block["sha256"] = sha256_hex
    if extends:
        block["extends"] = [str(item) for item in extends]
    if rules_applied:
        block["rules_applied"] = [str(item) for item in rules_applied]
    if withheld:
        block["withheld"] = [dict(item) for item in withheld]
    if commitments is not None:
        block["commitments"] = int(commitments)
    if note:
        block["note"] = note
    return block


def auditum(
    *,
    listenings: Iterable[dict[str, Any]],
    disagreements: Iterable[dict[str, Any]] | None = None,
    honest_absences: Iterable[dict[str, Any]] | None = None,
    actions: Iterable[dict[str, Any]] | None = None,
    revision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the v1.4 addressable auditum block.

    Each listening remains attributable to one listener and report namespace;
    disagreement is preserved between listening ids rather than collapsed into
    consensus. Action proposals carry authority separately from capability.
    "Tokenized" in the protocol means structured and referenceable, never a
    financial token.
    """
    listening_items = [dict(item) for item in listenings]
    if not listening_items:
        raise ValueError("auditum: at least one listening is required")

    required_listening = (
        "listening_id",
        "listener_id",
        "listener_type",
        "created_at",
        "report_namespace",
        "contract",
    )
    listening_ids: set[str] = set()
    for index, item in enumerate(listening_items):
        for key in required_listening:
            if not isinstance(item.get(key), str) or not item[key]:
                raise ValueError(f"auditum: listenings[{index}].{key} must be a non-empty string")
        if item["listener_type"] not in AUDITUM_LISTENER_TYPES:
            raise ValueError(
                f"auditum: listenings[{index}].listener_type must be one of "
                f"{', '.join(AUDITUM_LISTENER_TYPES)}"
            )
        if item["listening_id"] in listening_ids:
            raise ValueError(f"auditum: duplicate listening_id {item['listening_id']!r}")
        listening_ids.add(item["listening_id"])

    disagreement_items = [dict(item) for item in disagreements or []]
    for index, item in enumerate(disagreement_items):
        ids = item.get("listening_ids")
        if not isinstance(ids, list) or len(set(ids)) < 2:
            raise ValueError(f"auditum: disagreements[{index}] needs at least two listening_ids")
        if not set(ids).issubset(listening_ids):
            raise ValueError(f"auditum: disagreements[{index}] references an unknown listening_id")
        if item.get("status") not in AUDITUM_DISAGREEMENT_STATUSES:
            raise ValueError(
                f"auditum: disagreements[{index}].status must be one of "
                f"{', '.join(AUDITUM_DISAGREEMENT_STATUSES)}"
            )
        positions = item.get("positions")
        if not isinstance(positions, list) or len(positions) < 2:
            raise ValueError(f"auditum: disagreements[{index}] needs at least two positions")
        if any(position.get("listening_id") not in ids for position in positions if isinstance(position, dict)):
            raise ValueError(f"auditum: disagreements[{index}] position is not attributable to its listenings")

    absence_items = [dict(item) for item in honest_absences or []]
    for index, item in enumerate(absence_items):
        if item.get("kind") not in AUDITUM_ABSENCE_KINDS:
            raise ValueError(
                f"auditum: honest_absences[{index}].kind must be one of "
                f"{', '.join(AUDITUM_ABSENCE_KINDS)}"
            )

    action_items = [dict(item) for item in actions or []]
    for index, item in enumerate(action_items):
        if item.get("status") not in AUDITUM_ACTION_STATUSES:
            raise ValueError(
                f"auditum: actions[{index}].status must be one of "
                f"{', '.join(AUDITUM_ACTION_STATUSES)}"
            )

    block: dict[str, Any] = {
        "contract": AUDITUM_CONTRACT,
        "listenings": listening_items,
        "disagreements": disagreement_items,
        "honest_absences": absence_items,
        "actions": action_items,
    }
    if revision:
        block["revision"] = dict(revision)
    return block


# ---------------------------------------------------------------------------
# the shared akousmata store
# ---------------------------------------------------------------------------

def default_store_path() -> Path:
    env = os.getenv("AKOUSMATA_PATH")
    if env:
        return Path(env).expanduser()
    # Preserve an existing adjacent navigator store in source-checkout layouts.
    source_sibling = Path(__file__).resolve().parents[3].parent / "akousmata"
    if (source_sibling / "index.sqlite").exists():
        return source_sibling
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "akousmata"
    if os.name == "nt":
        base = Path(os.getenv("LOCALAPPDATA") or (Path.home() / "AppData" / "Local"))
        return base / "akousmata"
    base = Path(os.getenv("XDG_DATA_HOME") or (Path.home() / ".local" / "share"))
    return base / "akousmata"


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
            CREATE INDEX IF NOT EXISTS idx_akousmata_created ON akousmata(created_at);
            """
        )
        # v0.3: location columns, hoisted from record["location"] so the
        # listening map never scans JSON. Existing stores migrate in place.
        columns = {row["name"] for row in self.conn.execute("PRAGMA table_info(akousmata)")}
        if "lat" not in columns:
            self.conn.execute("ALTER TABLE akousmata ADD COLUMN lat REAL")
            self.conn.execute("ALTER TABLE akousmata ADD COLUMN lon REAL")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_akousmata_location ON akousmata(lat, lon)")
        # v0.4: covenant identity, hoisted from record["covenant"]["id"] so
        # "everything listened under this covenant" is an indexed question.
        if "covenant_id" not in columns:
            self.conn.execute("ALTER TABLE akousmata ADD COLUMN covenant_id TEXT")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_akousmata_covenant ON akousmata(covenant_id)")
        # v0.5 / akousma v1.4: hoist only audit indexes. Full reports stay in
        # the canonical JSON record, preserving open-record round trips.
        if "auditum_contract" not in columns:
            self.conn.execute("ALTER TABLE akousmata ADD COLUMN auditum_contract TEXT")
        if "listening_count" not in columns:
            self.conn.execute("ALTER TABLE akousmata ADD COLUMN listening_count INTEGER NOT NULL DEFAULT 0")
        if "disagreement_count" not in columns:
            self.conn.execute("ALTER TABLE akousmata ADD COLUMN disagreement_count INTEGER NOT NULL DEFAULT 0")
        if "honest_absence_count" not in columns:
            self.conn.execute("ALTER TABLE akousmata ADD COLUMN honest_absence_count INTEGER NOT NULL DEFAULT 0")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_akousmata_auditum ON akousmata(auditum_contract)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_akousmata_disagreement ON akousmata(disagreement_count)")
        self.conn.commit()

    @staticmethod
    def _latlon(record: dict[str, Any]) -> tuple[float | None, float | None]:
        loc = record.get("location") or {}
        lat, lon = loc.get("lat"), loc.get("lon")
        if isinstance(lat, (int, float)) and isinstance(lon, (int, float)):
            return float(lat), float(lon)
        return None, None

    @staticmethod
    def _covenant_id(record: dict[str, Any]) -> str | None:
        block = record.get("covenant") or {}
        value = block.get("id")
        return str(value) if isinstance(value, str) and value else None

    @staticmethod
    def _auditum_index(record: dict[str, Any]) -> tuple[str | None, int, int, int]:
        block = record.get("auditum")
        if not isinstance(block, dict):
            return None, 0, 0, 0
        contract = block.get("contract")
        listenings = block.get("listenings")
        disagreements = block.get("disagreements")
        absences = block.get("honest_absences")
        return (
            str(contract) if isinstance(contract, str) and contract else None,
            len(listenings) if isinstance(listenings, list) else 0,
            len(disagreements) if isinstance(disagreements, list) else 0,
            len(absences) if isinstance(absences, list) else 0,
        )

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
        lat, lon = self._latlon(record)
        auditum_contract, listening_count, disagreement_count, honest_absence_count = self._auditum_index(record)
        self.conn.execute(
            """INSERT OR REPLACE INTO akousmata
               (akousma_id, created_at, originating_app, source_type, origin,
                content_hash, session_id, lat, lon, covenant_id, auditum_contract,
                listening_count, disagreement_count, honest_absence_count, record)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                rid,
                record["created_at"],
                record["provenance"].get("originating_app"),
                record["provenance"].get("source_type"),
                record["provenance"].get("origin"),
                record.get("audio", {}).get("content_hash"),
                record.get("session_id"),
                lat,
                lon,
                self._covenant_id(record),
                auditum_contract,
                listening_count,
                disagreement_count,
                honest_absence_count,
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
        has_location: bool | None = None,
        covenant_id: str | None = None,
        has_auditum: bool | None = None,
        has_disagreement: bool | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        clauses, args = [], []
        for col, val in (
            ("originating_app", originating_app),
            ("source_type", source_type),
            ("origin", origin),
            ("session_id", session_id),
            ("content_hash", content_hash),
            ("covenant_id", covenant_id),
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
        if has_location is True:
            clauses.append("lat IS NOT NULL AND lon IS NOT NULL")
        elif has_location is False:
            clauses.append("(lat IS NULL OR lon IS NULL)")
        if has_auditum is True:
            clauses.append("auditum_contract IS NOT NULL")
        elif has_auditum is False:
            clauses.append("auditum_contract IS NULL")
        if has_disagreement is True:
            clauses.append("disagreement_count>0")
        elif has_disagreement is False:
            clauses.append("disagreement_count=0")
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        args.append(limit)
        # Column names and clauses above come only from fixed literals; all caller values are bound parameters.
        rows = self.conn.execute(  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
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
        if rel_type is None:
            rows = self.conn.execute(
                "SELECT from_id, rel_type, to_id FROM relation_edges WHERE from_id=? OR to_id=?",
                (akousma_id, akousma_id),
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT from_id, rel_type, to_id FROM relation_edges WHERE (from_id=? OR to_id=?) AND rel_type=?",
                (akousma_id, akousma_id, rel_type),
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
        try:
            # v0.3 fast path: let SQLite's JSON1 unnest tags instead of
            # parsing every record blob in Python (O(n) json.loads).
            rows = self.conn.execute(
                """SELECT je.value AS tag, COUNT(*) AS count
                   FROM akousmata, json_each(akousmata.record, '$.tags') AS je
                   GROUP BY je.value ORDER BY count DESC, tag ASC"""
            ).fetchall()
            return [{"tag": str(row["tag"]), "count": row["count"]} for row in rows]
        except sqlite3.OperationalError:
            counts: dict[str, int] = {}
            for row in self.conn.execute("SELECT record FROM akousmata").fetchall():
                for tag in json.loads(row["record"]).get("tags") or []:
                    counts[str(tag)] = counts.get(str(tag), 0) + 1
            return [
                {"tag": tag, "count": count}
                for tag, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
            ]

    def locations(self, *, limit: int = 10000) -> list[dict[str, Any]]:
        """Records that carry a location, newest first — the listening map's feed."""
        rows = self.conn.execute(
            """SELECT record FROM akousmata
               WHERE lat IS NOT NULL AND lon IS NOT NULL
               ORDER BY created_at DESC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [json.loads(r["record"]) for r in rows]

    def near(
        self,
        lat: float,
        lon: float,
        *,
        radius_km: float = 1.0,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Located records within ``radius_km`` of a point, nearest first.
        Bounding-box prefilter on the indexed lat/lon columns, exact
        great-circle (haversine) distance in Python. Boxes that would cross
        the antimeridian fall back to a latitude-band scan."""
        dlat = radius_km / 111.32
        dlon = radius_km / (111.32 * max(math.cos(math.radians(lat)), 0.01))
        if -180.0 <= lon - dlon and lon + dlon <= 180.0:
            rows = self.conn.execute(
                """SELECT record, lat, lon FROM akousmata
                   WHERE lat IS NOT NULL AND lon IS NOT NULL
                   AND lat BETWEEN ? AND ? AND lon BETWEEN ? AND ?""",
                (lat - dlat, lat + dlat, lon - dlon, lon + dlon),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT record, lat, lon FROM akousmata
                   WHERE lat IS NOT NULL AND lon IS NOT NULL
                   AND lat BETWEEN ? AND ?""",
                (lat - dlat, lat + dlat),
            ).fetchall()

        def haversine_km(row: sqlite3.Row) -> float:
            phi1, phi2 = math.radians(row["lat"]), math.radians(lat)
            dphi = math.radians(lat - row["lat"])
            dlmb = math.radians(lon - row["lon"])
            h = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmb / 2) ** 2
            return 2 * 6371.0088 * math.asin(math.sqrt(h))

        measured = ((haversine_km(row), row) for row in rows)
        scored = sorted(
            (pair for pair in measured if pair[0] <= radius_km),
            key=lambda pair: pair[0],
        )
        return [json.loads(row["record"]) for _, row in scored[:limit]]

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
            lat, lon = self._latlon(record)
            auditum_contract, listening_count, disagreement_count, honest_absence_count = self._auditum_index(record)
            self.conn.execute(
                """UPDATE akousmata
                   SET lat=?, lon=?, covenant_id=?, auditum_contract=?,
                       listening_count=?, disagreement_count=?, honest_absence_count=?
                   WHERE akousma_id=?""",
                (
                    lat,
                    lon,
                    self._covenant_id(record),
                    auditum_contract,
                    listening_count,
                    disagreement_count,
                    honest_absence_count,
                    rid,
                ),
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

    def __exit__(self, *_exc: object) -> None:
        self.close()


__all__ = [
    "SCHEMA_VERSION",
    "AUDITUM_CONTRACT",
    "RELATION_TYPES",
    "PIPELINE_EFFECTS",
    "LOCATION_SOURCES",
    "CAPTURE_DIRECTIONS",
    "AUDITUM_LISTENER_TYPES",
    "AUDITUM_ABSENCE_KINDS",
    "AUDITUM_DISAGREEMENT_STATUSES",
    "AUDITUM_ACTION_STATUSES",
    "new_id",
    "load_schema",
    "validation_errors",
    "is_valid",
    "new_akousma",
    "relation",
    "add_listening",
    "location",
    "capture",
    "covenant",
    "auditum",
    "default_store_path",
    "AkousmataStore",
]
