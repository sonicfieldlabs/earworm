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

SCHEMA_VERSION = "1.6.0"
AUDITUM_CONTRACT = "earworm/auditum/v2"
LEGACY_AUDITUM_CONTRACT = "earworm/auditum/v1"
FORGETTING_RECEIPT_CONTRACT = "earworm/forgetting-receipt/v1"
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

AUDITUM_LISTENER_TYPES = (
    "human", "agent", "hybrid", "community", "institution", "sensor",
    "habitat", "other_animal", "ensemble", "other",
)
AUDITUM_ABSENCE_KINDS = (
    "unavailable",
    "withheld",
    "refused",
    "not_retained",
    "forgotten",
)
AUDITUM_DISAGREEMENT_STATUSES = ("preserved", "resolved", "undetermined")
AUDITUM_ACTION_STATUSES = ("proposed", "authorized", "refused", "executed", "failed", "reverted")
AUDITUM_DECISION_GATES = ("input", "capture", "inference", "memory", "output", "disclosure", "retention", "action")
AUDITUM_DECISION_OUTCOMES = ("proceed", "pause", "defer", "abstain", "refuse", "withhold", "forget", "do_not_act")

RECORD_CLASSES = (
    "human",
    "agent",
    "hybrid",
    "plural_other",
    "decision_only",
    "legacy",
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


def _has_precapture_stop(auditum_block: dict[str, Any]) -> bool:
    decisions = auditum_block.get("route_decisions")
    return isinstance(decisions, list) and any(
        isinstance(item, dict)
        and item.get("gate") in {"input", "capture"}
        and item.get("outcome") in {"pause", "defer", "abstain", "refuse", "withhold"}
        for item in decisions
    )


def _has_raw_audio_absence(auditum_block: dict[str, Any]) -> bool:
    absences = auditum_block.get("honest_absences")
    return isinstance(absences, list) and any(
        isinstance(item, dict)
        and item.get("kind") in {"unavailable", "not_retained"}
        and item.get("subject") == "raw audio"
        for item in absences
    )


def listener_types(record: dict[str, Any]) -> tuple[str, ...]:
    """Return the canonical attributable listener types in stable vocabulary order.

    This is a lossless facet: community, institution, sensor, habitat,
    other-animal, ensemble, and other listening are never relabelled as human
    or machine.
    """
    auditum_block = record.get("auditum")
    listenings = auditum_block.get("listenings") if isinstance(auditum_block, dict) else None
    if not isinstance(listenings, list):
        return ()
    present = {
        item.get("listener_type")
        for item in listenings
        if isinstance(item, dict) and item.get("listener_type") in AUDITUM_LISTENER_TYPES
    }
    return tuple(listener_type for listener_type in AUDITUM_LISTENER_TYPES if listener_type in present)


def record_class(record: dict[str, Any]) -> str:
    """Derive a coarse navigation class without replacing listener types.

    ``plural_other`` means that at least one attributable listener is outside
    the human/agent/hybrid triad; callers must inspect :func:`listener_types`
    for the preserved canonical types. Records without a usable attributable
    auditum remain ``legacy``.
    """
    auditum_block = record.get("auditum")
    if not isinstance(auditum_block, dict):
        return "legacy"
    listenings = auditum_block.get("listenings")
    if not isinstance(listenings, list):
        return "legacy"
    if not listenings:
        return "decision_only" if _has_precapture_stop(auditum_block) else "legacy"
    if any(
        not isinstance(item, dict) or item.get("listener_type") not in AUDITUM_LISTENER_TYPES
        for item in listenings
    ):
        return "legacy"
    types = set(listener_types(record))
    if types == {"human"}:
        return "human"
    if types == {"agent"}:
        return "agent"
    if types and types.issubset({"human", "agent", "hybrid"}):
        return "hybrid"
    return "plural_other"


def revision_of(record: dict[str, Any]) -> str | None:
    """Return the directly revised akousma id, if this is a revision record."""
    auditum_block = record.get("auditum")
    revision = auditum_block.get("revision") if isinstance(auditum_block, dict) else None
    target = revision.get("revises_akousma_id") if isinstance(revision, dict) else None
    return target if isinstance(target, str) and target else None


def _fallback_validation_errors(record: dict[str, Any]) -> list[str]:
    """Validate the record's required structural boundary without jsonschema."""
    errors: list[str] = []
    for key in ("akousma_id", "schema_version", "created_at", "provenance", "lineage"):
        if key not in record:
            errors.append(f"<root>: '{key}' is required")

    audio = record.get("audio")
    if audio is not None:
        if not isinstance(audio, dict):
            errors.append("audio: must be an object")
        elif "asset_id" not in audio:
            errors.append("audio: 'asset_id' is required")
    else:
        auditum_block = record.get("auditum")
        listenings = auditum_block.get("listenings") if isinstance(auditum_block, dict) else None
        common_valid = (
            isinstance(record.get("subject"), str)
            and bool(record["subject"].strip())
            and isinstance(auditum_block, dict)
            and auditum_block.get("contract") == AUDITUM_CONTRACT
            and isinstance(listenings, list)
        )
        decision_only = common_valid and not listenings and _has_precapture_stop(auditum_block)
        listening_only = common_valid and bool(listenings) and _has_raw_audio_absence(auditum_block)
        if not decision_only and not listening_only:
            errors.append(
                "<root>: audio, a decision-only subject/auditum, or a listening-only "
                "subject/auditum with an unavailable/not_retained raw-audio absence is required"
            )

    if isinstance(record.get("lineage"), dict) and "parent_akousma_ids" not in record["lineage"]:
        errors.append("lineage: 'parent_akousma_ids' is required")
    return errors


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
        return _fallback_validation_errors(record)


def is_valid(record: dict[str, Any]) -> bool:
    return not validation_errors(record)


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def new_akousma(
    *,
    audio: dict[str, Any] | None = None,
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
    subject: str | None = None,
) -> dict[str, Any]:
    """Build an akousma v1.6 record.

    Normal records require ``audio.asset_id``. A decision-only record may omit
    audio only when ``subject`` is category-level text and an auditum/v2
    capture/input decision records why the ear never opened. A listening-only
    record may omit audio when it has an attributable auditum/v2 listening and
    an honest absence saying raw audio was unavailable or not retained.
    """
    if audio is not None and (not isinstance(audio.get("asset_id"), str) or not audio["asset_id"]):
        raise ValueError("new_akousma: audio.asset_id is required when audio is supplied")
    if audio is None:
        listenings = auditum.get("listenings") if isinstance(auditum, dict) else None
        common_valid = (
            isinstance(subject, str)
            and bool(subject.strip())
            and isinstance(auditum, dict)
            and auditum.get("contract") == AUDITUM_CONTRACT
            and isinstance(listenings, list)
        )
        decision_only = common_valid and not listenings and _has_precapture_stop(auditum)
        listening_only = common_valid and bool(listenings) and _has_raw_audio_absence(auditum)
        if not decision_only and not listening_only:
            raise ValueError(
                "new_akousma: audio may be omitted only for a decision-only auditum/v2 "
                "input/capture stop, or for a listening-only auditum/v2 record with an "
                "unavailable/not_retained raw-audio absence"
            )
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
    if audio is not None:
        record["audio"] = audio
    if subject:
        record["subject"] = subject
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


def route_decision(
    decision_id: str,
    *,
    gate: str,
    outcome: str,
    subject: str,
    reason: str,
    actor: str,
    decided_at: str | None = None,
    authority_mode: str = "observe_only",
    listening_id: str | None = None,
    producer_contract: str | None = None,
    producer_decision_ref: str | None = None,
    covenant_ref: str | None = None,
    granted_by: str | None = None,
    requires_confirmation: bool = True,
    reversible: bool = True,
    note: str | None = None,
) -> dict[str, Any]:
    """Build one addressable auditum/v2 gate decision."""
    if gate not in AUDITUM_DECISION_GATES:
        raise ValueError(f"route_decision: gate must be one of {', '.join(AUDITUM_DECISION_GATES)}")
    if outcome not in AUDITUM_DECISION_OUTCOMES:
        raise ValueError(f"route_decision: outcome must be one of {', '.join(AUDITUM_DECISION_OUTCOMES)}")
    decision: dict[str, Any] = {
        "decision_id": decision_id,
        "gate": gate,
        "outcome": outcome,
        "subject": subject,
        "reason": reason,
        "decided_at": decided_at or _utc_now(),
        "authority": {
            "mode": authority_mode,
            "actor": actor,
            "requires_confirmation": bool(requires_confirmation),
            "reversible": bool(reversible),
        },
    }
    for key, value in (
        ("listening_id", listening_id),
        ("producer_contract", producer_contract),
        ("producer_decision_ref", producer_decision_ref),
        ("note", note),
    ):
        if value is not None:
            decision[key] = value
    for key, value in (("covenant_ref", covenant_ref), ("granted_by", granted_by)):
        if value is not None:
            decision["authority"][key] = value
    return decision


def auditum(
    *,
    listenings: Iterable[dict[str, Any]] | None = None,
    disagreements: Iterable[dict[str, Any]] | None = None,
    honest_absences: Iterable[dict[str, Any]] | None = None,
    actions: Iterable[dict[str, Any]] | None = None,
    route_decisions: Iterable[dict[str, Any]] | None = None,
    ensemble: dict[str, Any] | None = None,
    revision: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the v1.6 addressable auditum/v2 block.

    Each listening remains attributable to one listener and report namespace;
    disagreement is preserved between listening ids rather than collapsed into
    consensus. Action proposals carry authority separately from capability.
    "Tokenized" in the protocol means structured and referenceable, never a
    financial token.
    """
    listening_items = [dict(item) for item in listenings or []]

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
        if item.get("status") == "resolved" and (
            not isinstance(item.get("resolution_note"), str)
            or not item["resolution_note"].strip()
        ):
            raise ValueError(
                f"auditum: disagreements[{index}].resolution_note must be a non-empty string when resolved"
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

    decision_items = [dict(item) for item in route_decisions or []]
    if not decision_items:
        raise ValueError("auditum: auditum/v2 requires at least one route decision")
    decision_ids: set[str] = set()
    required_decision = ("decision_id", "gate", "outcome", "subject", "reason", "decided_at", "authority")
    for index, item in enumerate(decision_items):
        for key in required_decision:
            if key not in item:
                raise ValueError(f"auditum: route_decisions[{index}].{key} is required")
        decision_id = item.get("decision_id")
        if not isinstance(decision_id, str) or not decision_id:
            raise ValueError(f"auditum: route_decisions[{index}].decision_id must be a non-empty string")
        if decision_id in decision_ids:
            raise ValueError(f"auditum: duplicate decision_id {decision_id!r}")
        decision_ids.add(decision_id)
        if item.get("gate") not in AUDITUM_DECISION_GATES:
            raise ValueError(f"auditum: route_decisions[{index}].gate must be one of {', '.join(AUDITUM_DECISION_GATES)}")
        if item.get("outcome") not in AUDITUM_DECISION_OUTCOMES:
            raise ValueError(f"auditum: route_decisions[{index}].outcome must be one of {', '.join(AUDITUM_DECISION_OUTCOMES)}")
        if item.get("listening_id") is not None and item["listening_id"] not in listening_ids:
            raise ValueError(f"auditum: route_decisions[{index}] references an unknown listening_id")
        authority = item.get("authority")
        if not isinstance(authority, dict) or not isinstance(authority.get("actor"), str) or not authority["actor"]:
            raise ValueError(f"auditum: route_decisions[{index}].authority.actor must be a non-empty string")

    if not listening_items and not any(
        item.get("gate") in {"input", "capture"}
        and item.get("outcome") in {"pause", "defer", "abstain", "refuse", "withhold"}
        for item in decision_items
    ):
        raise ValueError("auditum: an empty listening list requires an input or capture stop decision")

    block: dict[str, Any] = {
        "contract": AUDITUM_CONTRACT,
        "listenings": listening_items,
        "disagreements": disagreement_items,
        "honest_absences": absence_items,
        "actions": action_items,
        "route_decisions": decision_items,
    }
    if ensemble:
        listening_refs = ensemble.get("listening_ids") if isinstance(ensemble, dict) else None
        if not isinstance(listening_refs, list) or len(set(listening_refs)) < 2 or not set(listening_refs).issubset(listening_ids):
            raise ValueError("auditum: ensemble requires at least two known listening_ids")
        if ensemble.get("kind") == "ear_swarm":
            if not ensemble.get("influence_edges") or ensemble.get("permissions_preserved") is not True or ensemble.get("disagreements_preserved") is not True:
                raise ValueError("auditum: ear_swarm requires influence plus preserved permissions and disagreements")
            for edge in ensemble["influence_edges"]:
                if not isinstance(edge, dict) or edge.get("from_listening_id") not in listening_ids or edge.get("to_listening_id") not in listening_ids:
                    raise ValueError("auditum: ear_swarm influence edges must reference known listenings")
        block["ensemble"] = dict(ensemble)
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
        listener_index_existed = self.conn.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='listener_type_index'"
        ).fetchone() is not None
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
              record_class    TEXT NOT NULL DEFAULT 'legacy',
              revision_of     TEXT,
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
            CREATE TABLE IF NOT EXISTS listener_type_index (
              akousma_id   TEXT NOT NULL,
              listener_type TEXT NOT NULL,
              PRIMARY KEY (akousma_id, listener_type)
            );
            CREATE INDEX IF NOT EXISTS idx_listener_type ON listener_type_index(listener_type, akousma_id);
            CREATE INDEX IF NOT EXISTS idx_akousmata_hash ON akousmata(content_hash);
            CREATE INDEX IF NOT EXISTS idx_akousmata_created ON akousmata(created_at);
            CREATE TABLE IF NOT EXISTS forgetting_receipts (
              receipt_id             TEXT PRIMARY KEY,
              akousma_id             TEXT NOT NULL,
              created_at             TEXT NOT NULL,
              actor                  TEXT NOT NULL,
              reason                 TEXT NOT NULL,
              receipt                TEXT NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_forgetting_akousma ON forgetting_receipts(akousma_id, created_at);
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
        if "route_decision_count" not in columns:
            self.conn.execute("ALTER TABLE akousmata ADD COLUMN route_decision_count INTEGER NOT NULL DEFAULT 0")
        if "stop_decision_count" not in columns:
            self.conn.execute("ALTER TABLE akousmata ADD COLUMN stop_decision_count INTEGER NOT NULL DEFAULT 0")
        # v0.7 / akousma v1.6: listener types stay lossless in a normalized
        # index; record_class is only a coarse navigator facet. Revision
        # targets are hoisted for chain/head lookups. Existing JSON is never
        # rewritten during migration.
        derived_index_changed = not listener_index_existed
        if "record_class" not in columns:
            self.conn.execute("ALTER TABLE akousmata ADD COLUMN record_class TEXT NOT NULL DEFAULT 'legacy'")
            derived_index_changed = True
        if "revision_of" not in columns:
            self.conn.execute("ALTER TABLE akousmata ADD COLUMN revision_of TEXT")
            derived_index_changed = True
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_akousmata_auditum ON akousmata(auditum_contract)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_akousmata_disagreement ON akousmata(disagreement_count)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_akousmata_decision ON akousmata(route_decision_count, stop_decision_count)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_akousmata_record_class ON akousmata(record_class, created_at)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_akousmata_revision_of ON akousmata(revision_of)")
        if derived_index_changed:
            self._reindex_derived_metadata()
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
    def _auditum_index(record: dict[str, Any]) -> tuple[str | None, int, int, int, int, int]:
        block = record.get("auditum")
        if not isinstance(block, dict):
            return None, 0, 0, 0, 0, 0
        contract = block.get("contract")
        listenings = block.get("listenings")
        disagreements = block.get("disagreements")
        absences = block.get("honest_absences")
        decisions = block.get("route_decisions")
        stop_outcomes = {"pause", "defer", "abstain", "refuse", "withhold", "forget", "do_not_act"}
        return (
            str(contract) if isinstance(contract, str) and contract else None,
            len(listenings) if isinstance(listenings, list) else 0,
            len(disagreements) if isinstance(disagreements, list) else 0,
            len(absences) if isinstance(absences, list) else 0,
            len(decisions) if isinstance(decisions, list) else 0,
            sum(1 for item in decisions if isinstance(item, dict) and item.get("outcome") in stop_outcomes) if isinstance(decisions, list) else 0,
        )

    def _replace_listener_type_index(self, akousma_id: str, types: Iterable[str]) -> None:
        self.conn.execute("DELETE FROM listener_type_index WHERE akousma_id=?", (akousma_id,))
        self.conn.executemany(
            "INSERT OR IGNORE INTO listener_type_index (akousma_id, listener_type) VALUES (?,?)",
            ((akousma_id, listener_type) for listener_type in types),
        )

    def _reindex_derived_metadata(self) -> None:
        """Rebuild v0.7 facets without changing canonical record JSON."""
        rows = self.conn.execute("SELECT akousma_id, record FROM akousmata").fetchall()
        self.conn.execute("DELETE FROM listener_type_index")
        for row in rows:
            try:
                record = json.loads(row["record"])
            except (TypeError, json.JSONDecodeError):
                self.conn.execute(
                    "UPDATE akousmata SET record_class='legacy', revision_of=NULL WHERE akousma_id=?",
                    (row["akousma_id"],),
                )
                continue
            if not isinstance(record, dict):
                self.conn.execute(
                    "UPDATE akousmata SET record_class='legacy', revision_of=NULL WHERE akousma_id=?",
                    (row["akousma_id"],),
                )
                continue
            self.conn.execute(
                "UPDATE akousmata SET record_class=?, revision_of=? WHERE akousma_id=?",
                (record_class(record), revision_of(record), row["akousma_id"]),
            )
            self._replace_listener_type_index(row["akousma_id"], listener_types(record))

    @staticmethod
    def _protected_account(record: dict[str, Any]) -> dict[str, Any]:
        """Return the listening/account fields that an in-place edit may not rewrite.

        Curators may still update tags, annotations, summary, location, consent,
        rights, extensions, and typed kinship relations. A changed listening or
        causal account must use a fresh id and an ``auditum.revision`` link.
        """
        provenance = record.get("provenance") if isinstance(record.get("provenance"), dict) else {}
        lineage = record.get("lineage") if isinstance(record.get("lineage"), dict) else {}
        return {
            "schema_version": record.get("schema_version"),
            "created_at": record.get("created_at"),
            "audio": record.get("audio"),
            "subject": record.get("subject"),
            "listening": record.get("listening"),
            "auditum": record.get("auditum"),
            "provenance_account": {
                key: provenance.get(key)
                for key in (
                    "provenance_id",
                    "source_type",
                    "origin",
                    "originating_app",
                    "device",
                    "provider",
                    "model_id",
                    "seed",
                    "created_at",
                    "capture_conditions",
                    "pipeline_effects",
                )
            },
            "causal_lineage": {
                key: lineage.get(key)
                for key in (
                    "parent_akousma_ids",
                    "operation",
                    "prompt",
                    "model",
                    "params",
                    "event_ids",
                )
            },
        }

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
        if self.forgotten(rid) is not None:
            raise ValueError(f"akousma {rid!r} has a forgetting receipt and cannot be silently resurrected")
        revision = record.get("auditum", {}).get("revision") if isinstance(record.get("auditum"), dict) else None
        revision_target = revision_of(record)
        if isinstance(revision, dict):
            target = revision_target
            if target == rid:
                raise ValueError("an auditum revision must use a fresh akousma_id, not revise itself")
            if not isinstance(target, str) or self.get(target) is None:
                raise ValueError(f"auditum revision target {target!r} is not present in this store")
        existing = self.get(rid)
        if existing is not None and self._protected_account(existing) != self._protected_account(record):
            raise ValueError(
                f"akousma {rid!r} has an existing listening account; create a new record with auditum.revision instead of overwriting it"
            )
        lat, lon = self._latlon(record)
        auditum_contract, listening_count, disagreement_count, honest_absence_count, route_decision_count, stop_decision_count = self._auditum_index(record)
        types = listener_types(record)
        derived_class = record_class(record)
        self.conn.execute(
            """INSERT OR REPLACE INTO akousmata
               (akousma_id, created_at, originating_app, source_type, origin,
                content_hash, session_id, lat, lon, covenant_id, auditum_contract,
                listening_count, disagreement_count, honest_absence_count,
                route_decision_count, stop_decision_count, record_class,
                revision_of, record)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
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
                route_decision_count,
                stop_decision_count,
                derived_class,
                revision_target,
                json.dumps(record),
            ),
        )
        self._replace_listener_type_index(rid, types)
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
        has_route_decision: bool | None = None,
        has_stop_decision: bool | None = None,
        listener_type: str | None = None,
        record_class: str | None = None,
        revision_of: str | None = None,
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
            ("record_class", record_class),
            ("revision_of", revision_of),
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
        if has_route_decision is True:
            clauses.append("route_decision_count>0")
        elif has_route_decision is False:
            clauses.append("route_decision_count=0")
        if has_stop_decision is True:
            clauses.append("stop_decision_count>0")
        elif has_stop_decision is False:
            clauses.append("stop_decision_count=0")
        if listener_type is not None:
            if listener_type not in AUDITUM_LISTENER_TYPES:
                raise ValueError(
                    f"query: listener_type must be one of {', '.join(AUDITUM_LISTENER_TYPES)}"
                )
            clauses.append(
                "EXISTS (SELECT 1 FROM listener_type_index AS lti "
                "WHERE lti.akousma_id=akousmata.akousma_id AND lti.listener_type=?)"
            )
            args.append(listener_type)
        if record_class is not None and record_class not in RECORD_CLASSES:
            raise ValueError(f"query: record_class must be one of {', '.join(RECORD_CLASSES)}")
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

    def revision_chain(self, akousma_id: str) -> list[dict[str, Any]]:
        """Return the complete revision component, oldest first.

        A component may branch; no branch is hidden or treated as consensus.
        Use :meth:`revision_heads` to inspect every leaf and
        :meth:`current_head` only when a unique head is required.
        """
        if self.get(akousma_id) is None:
            return []
        root = akousma_id
        seen: set[str] = set()
        while root not in seen:
            seen.add(root)
            row = self.conn.execute(
                "SELECT revision_of FROM akousmata WHERE akousma_id=?", (root,)
            ).fetchone()
            parent = row["revision_of"] if row else None
            if not isinstance(parent, str) or self.get(parent) is None:
                break
            root = parent

        component_ids: set[str] = set()
        stack = [root]
        while stack:
            current = stack.pop()
            if current in component_ids:
                continue
            component_ids.add(current)
            stack.extend(
                row["akousma_id"]
                for row in self.conn.execute(
                    "SELECT akousma_id FROM akousmata WHERE revision_of=?", (current,)
                ).fetchall()
            )
        placeholders = ",".join("?" for _ in component_ids)
        rows = self.conn.execute(
            f"SELECT record FROM akousmata WHERE akousma_id IN ({placeholders}) "  # nosemgrep: python.sqlalchemy.security.sqlalchemy-execute-raw-query.sqlalchemy-execute-raw-query
            "ORDER BY created_at ASC, akousma_id ASC",
            tuple(component_ids),
        ).fetchall()
        return [json.loads(row["record"]) for row in rows]

    def revision_heads(self, akousma_id: str) -> list[dict[str, Any]]:
        """Return every current leaf in a revision component, newest first."""
        chain = self.revision_chain(akousma_id)
        if not chain:
            return []
        component_ids = {record["akousma_id"] for record in chain}
        revised_ids = {
            target
            for record in chain
            if (target := revision_of(record)) in component_ids
        }
        return sorted(
            (record for record in chain if record["akousma_id"] not in revised_ids),
            key=lambda record: (record.get("created_at", ""), record["akousma_id"]),
            reverse=True,
        )

    def current_head(self, akousma_id: str) -> dict[str, Any] | None:
        """Return the unique revision head; reject divergent revision branches."""
        heads = self.revision_heads(akousma_id)
        if not heads:
            return None
        if len(heads) != 1:
            raise ValueError(
                f"akousma revision component for {akousma_id!r} has {len(heads)} current heads"
            )
        return heads[0]

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

    def forget_with_receipt(
        self,
        akousma_id: str,
        *,
        delete_audio: bool = False,
        actor: str = "operator",
        reason: str = "forget requested",
    ) -> dict[str, Any] | None:
        """Forget one record and return a content-free durable receipt.

        With ``delete_audio`` the content-addressed object is also removed —
        but only when no other record references the same content hash.
        Returns ``None`` when the record does not exist. Edges pointing AT the
        forgotten record are kept: absence is information, and ``verify()``
        reports them as dangling rather than erasing the trace. The receipt
        retains no summary, tags, location, audio URI, or forgotten content."""
        record = self.get(akousma_id)
        if record is None:
            return None
        audio_deleted = False
        shared_audio_preserved = False
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
                    audio_deleted = True
            elif uri.startswith("akousmata://objects/") and bool(others):
                shared_audio_preserved = True
        receipt = {
            "receipt_id": new_id("fgt"),
            "contract": FORGETTING_RECEIPT_CONTRACT,
            "akousma_id": akousma_id,
            "created_at": _utc_now(),
            "actor": actor,
            "reason": reason,
            "record_deleted": True,
            "audio_deletion_requested": bool(delete_audio),
            "audio_deleted": audio_deleted,
            "shared_audio_preserved": shared_audio_preserved,
            "recovery": (
                "The record and its unshared local audio are not recoverable from this store."
                if audio_deleted
                else "The record is not recoverable from this store; a shared audio object remains but is not reattached automatically."
                if shared_audio_preserved
                else "The record is not recoverable from this store."
            ),
        }
        self.conn.execute(
            "INSERT INTO forgetting_receipts (receipt_id, akousma_id, created_at, actor, reason, receipt) VALUES (?,?,?,?,?,?)",
            (receipt["receipt_id"], akousma_id, receipt["created_at"], actor, reason, json.dumps(receipt)),
        )
        self.conn.execute("DELETE FROM akousmata WHERE akousma_id=?", (akousma_id,))
        self.conn.execute("DELETE FROM lineage_edges WHERE child_id=?", (akousma_id,))
        self.conn.execute("DELETE FROM relation_edges WHERE from_id=?", (akousma_id,))
        self.conn.execute("DELETE FROM listener_type_index WHERE akousma_id=?", (akousma_id,))
        self.conn.commit()
        return receipt

    def forget(
        self,
        akousma_id: str,
        *,
        delete_audio: bool = False,
        actor: str = "operator",
        reason: str = "forget requested",
    ) -> bool:
        """Backward-compatible boolean wrapper around :meth:`forget_with_receipt`."""
        return self.forget_with_receipt(
            akousma_id,
            delete_audio=delete_audio,
            actor=actor,
            reason=reason,
        ) is not None

    def forgetting_receipts(self, akousma_id: str | None = None) -> list[dict[str, Any]]:
        """Return content-free forgetting receipts, newest first."""
        if akousma_id is None:
            rows = self.conn.execute(
                "SELECT receipt FROM forgetting_receipts ORDER BY created_at DESC, receipt_id DESC"
            ).fetchall()
        else:
            rows = self.conn.execute(
                "SELECT receipt FROM forgetting_receipts WHERE akousma_id=? ORDER BY created_at DESC, receipt_id DESC",
                (akousma_id,),
            ).fetchall()
        return [json.loads(row["receipt"]) for row in rows]

    def forgotten(self, akousma_id: str) -> dict[str, Any] | None:
        """Return the latest forgetting receipt for an identifier, if any."""
        row = self.conn.execute(
            "SELECT receipt FROM forgetting_receipts WHERE akousma_id=? ORDER BY created_at DESC, receipt_id DESC LIMIT 1",
            (akousma_id,),
        ).fetchone()
        return json.loads(row["receipt"]) if row else None

    # --- maintenance --------------------------------------------------------
    def reindex(self) -> int:
        """Rebuild edges and derived indexes without rewriting record JSON."""
        rows = self.conn.execute("SELECT record FROM akousmata").fetchall()
        self.conn.execute("DELETE FROM lineage_edges")
        self.conn.execute("DELETE FROM relation_edges")
        self.conn.execute("DELETE FROM listener_type_index")
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
            auditum_contract, listening_count, disagreement_count, honest_absence_count, route_decision_count, stop_decision_count = self._auditum_index(record)
            self.conn.execute(
                """UPDATE akousmata
                   SET lat=?, lon=?, covenant_id=?, auditum_contract=?,
                       listening_count=?, disagreement_count=?, honest_absence_count=?,
                       route_decision_count=?, stop_decision_count=?, record_class=?,
                       revision_of=?
                   WHERE akousma_id=?""",
                (
                    lat,
                    lon,
                    self._covenant_id(record),
                    auditum_contract,
                    listening_count,
                    disagreement_count,
                    honest_absence_count,
                    route_decision_count,
                    stop_decision_count,
                    record_class(record),
                    revision_of(record),
                    rid,
                ),
            )
            self._replace_listener_type_index(rid, listener_types(record))
        self.conn.commit()
        return len(rows)

    def verify(self) -> dict[str, list[str]]:
        """Integrity report — the archive of absence. Dangling links and missing
        audio are reported, never silently discarded: a dead record is still
        lineage information."""
        report: dict[str, list[str]] = {
            "dangling_parents": [],
            "dangling_relations": [],
            "dangling_revisions": [],
            "missing_audio": [],
            "invalid_records": [],
            "invalid_forgetting_receipts": [],
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
            revised = revision_of(record)
            if revised is not None and revised not in ids:
                report["dangling_revisions"].append(f"{rid} -> {revised}")
            uri = record.get("audio", {}).get("uri", "")
            if uri.startswith("akousmata://objects/"):
                path = self.resolve_uri(uri)
                if path is not None and not path.exists():
                    report["missing_audio"].append(f"{rid}: {uri}")
        forbidden_receipt_fields = {"record", "audio", "summary", "tags", "location", "subject", "content_hash", "uri"}
        for row in self.conn.execute("SELECT receipt_id, receipt FROM forgetting_receipts").fetchall():
            receipt = json.loads(row["receipt"])
            if receipt.get("contract") != FORGETTING_RECEIPT_CONTRACT or forbidden_receipt_fields.intersection(receipt):
                report["invalid_forgetting_receipts"].append(str(row["receipt_id"]))
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
    "LEGACY_AUDITUM_CONTRACT",
    "FORGETTING_RECEIPT_CONTRACT",
    "RELATION_TYPES",
    "PIPELINE_EFFECTS",
    "LOCATION_SOURCES",
    "CAPTURE_DIRECTIONS",
    "AUDITUM_LISTENER_TYPES",
    "AUDITUM_ABSENCE_KINDS",
    "AUDITUM_DISAGREEMENT_STATUSES",
    "AUDITUM_ACTION_STATUSES",
    "AUDITUM_DECISION_GATES",
    "AUDITUM_DECISION_OUTCOMES",
    "RECORD_CLASSES",
    "new_id",
    "load_schema",
    "validation_errors",
    "is_valid",
    "listener_types",
    "record_class",
    "revision_of",
    "new_akousma",
    "relation",
    "add_listening",
    "location",
    "capture",
    "covenant",
    "route_decision",
    "auditum",
    "default_store_path",
    "AkousmataStore",
]
