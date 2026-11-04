"""Listening circuits and run memory: the moves a listening loop made, and what a run remembers.

A circuit (``earworm/listening-circuit/v1``) rides on one record as
``extensions.earworm_listening_circuit``. Each step names the move that was chosen among the
offered ones, who chose it, the route it followed and its result. A run memory
(``earworm/run-memory/v1``) is folded from those circuits, one window at a time; it keeps counts
and states, never audio, account text or transcripts.

Both are additive: any akousma spec version may carry the extension, and a consumer that does not
negotiate the contract preserves it as an unknown extension.
"""
from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime
from typing import Any, Iterable

from jsonschema import Draft7Validator

from .listening_contracts import _ROOT, _errors, _nonfinite

LISTENING_CIRCUIT_CONTRACT = "earworm/listening-circuit/v1"
RUN_MEMORY_CONTRACT = "earworm/run-memory/v1"
CIRCUIT_EXTENSION = "earworm_listening_circuit"
RECENT_LIMIT = 64
SOURCE_LIMIT = 256

_CIRCUIT = Draft7Validator(json.loads((_ROOT / "listening-circuit.schema.json").read_text()))
_MEMORY = Draft7Validator(json.loads((_ROOT / "run-memory.schema.json").read_text()))

#: Moves that, once executed, produce a listening the step must point to.
_LISTENING_MOVES = {"relisten_same", "new_fragment", "switch_source"}


def _listening_ids(record: Any) -> set[str] | None:
    auditum = record.get("auditum") if isinstance(record, dict) else None
    if not isinstance(auditum, dict) or not isinstance(auditum.get("listenings"), list):
        return None
    return {
        str(item["listening_id"])
        for item in auditum["listenings"]
        if isinstance(item, dict) and item.get("listening_id")
    }


def listening_circuit_errors(value: Any, record: dict | None = None) -> list[str]:
    """Shape and coherence errors for one circuit ([] if valid).

    With ``record``, listening references must resolve to that record's auditum listenings.
    """
    if _nonfinite(value):
        return ["Listening circuit requires finite JSON numbers"]
    errors = _errors(_CIRCUIT, value)
    if errors:
        return errors
    known = _listening_ids(record) if record is not None else None
    if record is not None and known is None:
        errors.append("A circuit's record must carry an auditum with listenings")
    seen_steps: set[str] = set()
    for step in value["steps"]:
        sid = step["step_id"]
        where = f"steps[{sid}]"
        if sid in seen_steps:
            errors.append(f"{where}: duplicate step id")
        seen_steps.add(sid)
        offered = {}
        for candidate in step["offered"]:
            if candidate["id"] in offered:
                errors.append(f"{where}: duplicate offered candidate {candidate['id']}")
            offered[candidate["id"]] = candidate
        move, status, chosen = step["move"], step["outcome"]["status"], step["chosen"]
        if chosen is None:
            if move != "stop" and status not in {"refused", "blocked", "failed"}:
                errors.append(f"{where}: only a stop or an unexecuted step may choose nothing")
        elif chosen not in offered:
            errors.append(f"{where}: the chosen candidate was not offered")
        elif offered[chosen]["move"] != move:
            errors.append(f"{where}: the chosen candidate's move differs from the step's move")
        if (move == "sound") != (step["layer"] == "sounding"):
            errors.append(f"{where}: a sounding layer belongs to a sound move, and only to one")
        if move == "stop" and step["layer"] != "closing":
            errors.append(f"{where}: a stop closes the circuit")
        bounds = step.get("bounds") or {}
        if bounds.get("max_depth") is not None and step["depth"] > bounds["max_depth"]:
            errors.append(f"{where}: depth exceeds the declared maximum")
        if status == "executed":
            if move == "sound" and not step.get("to_akousma_id"):
                errors.append(f"{where}: an executed sound names the record of what was sounded")
            if move in _LISTENING_MOVES and not (step.get("to_listening_id") or step.get("to_akousma_id")):
                errors.append(f"{where}: an executed {move} names the listening or record it produced")
        if known is not None:
            refs = [("to_listening_id", step.get("to_listening_id"))]
            if not step.get("from_akousma_id"):
                refs.append(("from_listening_id", step.get("from_listening_id")))
            for key, ref in refs:
                if ref is not None and ref not in known:
                    errors.append(f"{where}: {key} does not resolve to this record's listenings")
    return errors


def circuit_record_errors(record: dict) -> list[str]:
    """Errors in a record's circuit extension; [] when the record carries none."""
    extensions = record.get("extensions") if isinstance(record, dict) else None
    if not isinstance(extensions, dict) or CIRCUIT_EXTENSION not in extensions:
        return []
    return listening_circuit_errors(extensions[CIRCUIT_EXTENSION], record)


def run_memory_errors(value: Any) -> list[str]:
    if _nonfinite(value):
        return ["Run memory requires finite JSON numbers"]
    errors = _errors(_MEMORY, value)
    if errors:
        return errors
    if _instant(value["updated_at"]) < _instant(value["started_at"]):
        errors.append("Run memory cannot be updated before it started")
    if len(value["sources"]) > SOURCE_LIMIT:
        errors.append(f"A run memory keeps at most {SOURCE_LIMIT} sources")
    windows = value["totals"]["windows"]
    for key, source in value["sources"].items():
        if source["last_window"] > windows:
            errors.append(f"sources[{key}]: last window is beyond the run's windows")
        if source["dwell"] > source["windows"] or source["visits"] > source["windows"]:
            errors.append(f"sources[{key}]: dwell and visits cannot exceed windows heard")
    if value.get("current_source") is not None and value["current_source"] not in value["sources"]:
        errors.append("The current source must be one the run has heard")
    return errors


def empty_run_memory(session_id: str, started_at: str) -> dict:
    memory = {
        "contract": RUN_MEMORY_CONTRACT,
        "session_id": session_id,
        "started_at": started_at,
        "updated_at": started_at,
        "revision": 0,
        "current_source": None,
        "sources": {},
        "totals": {"windows": 0, "steps": 0, "moves": {}, "layers": {}},
        "recent": [],
    }
    errors = run_memory_errors(memory)
    if errors:
        raise ValueError("; ".join(errors))
    return memory


def _instant(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def _count(table: dict, key: str, by: int = 1) -> None:
    table[key] = table.get(key, 0) + by


def fold_run_memory(
    memory: dict,
    *,
    at: str,
    source_key: str,
    akousma_id: str | None = None,
    circuit: dict | None = None,
    heard_as: Iterable[str] = (),
    modes: Iterable[str] = (),
    declined: bool = False,
    repeated: bool = False,
) -> dict:
    """Return a new run memory with one more window heard from ``source_key``.

    Pure: the given memory and circuit are not changed. A window from a source other than the
    current one opens a new visit. Every circuit step is counted by move and layer; the last step
    with a route becomes the source's last route.
    """
    errors = run_memory_errors(memory)
    if errors:
        raise ValueError("Invalid run memory: " + "; ".join(errors))
    if circuit is not None:
        errors = listening_circuit_errors(circuit)
        if errors:
            raise ValueError("Invalid listening circuit: " + "; ".join(errors))
        if circuit["run"]["session_id"] != memory["session_id"]:
            raise ValueError("The circuit belongs to another run")
        if circuit["run"]["source_key"] != source_key:
            raise ValueError("The circuit belongs to another source")
    if _instant(at) < _instant(memory["updated_at"]):
        raise ValueError("A run memory folds windows in time order")
    out = deepcopy(memory)
    out["totals"]["windows"] += 1
    window = out["totals"]["windows"]
    source = out["sources"].get(source_key)
    if source is None:
        source = out["sources"][source_key] = {
            "first_heard_at": at,
            "last_heard_at": at,
            "windows": 0,
            "visits": 0,
            "dwell": 0,
            "last_window": 0,
            "heard_as": {},
            "modes": {},
            "declined": 0,
            "repeated": 0,
            "soundings": 0,
            "last_route": None,
        }
    if out["current_source"] != source_key:
        source["visits"] += 1
        source["dwell"] = 0
    source["dwell"] += 1
    source["windows"] += 1
    source["last_heard_at"] = at
    source["last_window"] = window
    for kind in dict.fromkeys(heard_as):
        _count(source["heard_as"], str(kind))
    for mode in dict.fromkeys(modes):
        _count(source["modes"], str(mode))
    source["declined"] += int(bool(declined))
    source["repeated"] += int(bool(repeated))
    recent = out["recent"]
    steps = (circuit or {}).get("steps") or []
    for step in steps:
        out["totals"]["steps"] += 1
        _count(out["totals"]["moves"], step["move"])
        _count(out["totals"]["layers"], step["layer"])
        if step["move"] == "sound" and step["outcome"]["status"] == "executed":
            source["soundings"] += 1
        route = step.get("route")
        if route:
            source["last_route"] = {
                "primary": route["primary"],
                "secondary": route.get("secondary"),
                "corrective": route.get("corrective"),
                "confidence": route["confidence"],
            }
        recent.append(
            {
                "at": step["at"],
                "source_key": source_key,
                "move": step["move"],
                "layer": step["layer"],
                "akousma_id": step.get("to_akousma_id") or akousma_id,
                "primary": route["primary"] if route else None,
            }
        )
    if not steps:
        recent.append(
            {
                "at": at,
                "source_key": source_key,
                "move": "listen",
                "layer": "general",
                "akousma_id": akousma_id,
                "primary": None,
            }
        )
    del recent[:-RECENT_LIMIT]
    out["current_source"] = source_key
    out["updated_at"] = at
    out["revision"] += 1
    errors = run_memory_errors(out)
    if errors:
        raise ValueError("Folding produced an invalid run memory: " + "; ".join(errors))
    return out


def windows_since(memory: dict, source_key: str) -> int | None:
    """Windows the run has heard since this source was last heard, or None if never heard."""
    source = memory.get("sources", {}).get(source_key)
    if source is None:
        return None
    return memory["totals"]["windows"] - source["last_window"]
