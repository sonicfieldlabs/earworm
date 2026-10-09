"""Opt-in listening contracts. Canonical schemas are bundled for offline use."""
from __future__ import annotations

import json
import math
from copy import deepcopy
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator

LISTENING_ACCESS_CONTRACT = "earworm/listening-access/v1"
_ROOT = Path(__file__).parent
_ACCESS = Draft7Validator(json.loads((_ROOT / "listening-access.schema.json").read_text()))
_AUDITUM = json.loads((_ROOT / "akousma.schema.json").read_text())["$defs"]["auditum"]["properties"]
_LISTENING = Draft7Validator(_AUDITUM["listenings"]["items"])
_ENSEMBLE = Draft7Validator(_AUDITUM["ensemble"])


def _errors(validator: Draft7Validator, value: Any) -> list[str]:
    return [f"{'/'.join(str(p) for p in error.path) or '<root>'}: {error.message}"
            for error in validator.iter_errors(value)]


def _nonfinite(value: Any) -> bool:
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, dict):
        return any(_nonfinite(item) for item in value.values())
    if isinstance(value, list):
        return any(_nonfinite(item) for item in value)
    return False


def listening_access_errors(value: Any) -> list[str]:
    """Validate declarations; validity does not establish sensing or perception."""
    if _nonfinite(value):
        return ["<root>: numbers must be finite JSON numbers"]
    errors = _errors(_ACCESS, value)
    if errors:
        return errors
    for name, band_key in (("capture", "supported_band_hz"),
                           ("sampled_representation", "retained_band_hz"),
                           ("model_input", "effective_band_hz")):
        block = value[name]
        if block["status"] != "known":
            continue
        band = block[band_key]
        if band["lower"] >= band["upper"]:
            errors.append(f"{name}/{band_key}: lower must be less than upper")
        if "sample_rate_hz" in block and band["upper"] > block["sample_rate_hz"] / 2:
            errors.append(f"{name}/{band_key}: exceeds the declared representation's Nyquist limit")
    if value["model_input"]["status"] == "known":
        window = value["model_input"]["window_s"]
        if window["start"] >= window["end"]:
            errors.append("model_input/window_s: end must be greater than start")
    return errors


def assert_supported_contracts(required: list[str], supported: list[str]) -> None:
    """Reject unsupported required contracts before decisions, not opaque storage."""
    for label, items in (("required", required), ("supported", supported)):
        if not isinstance(items, list) or any(not isinstance(item, str) or not item.strip() for item in items):
            raise TypeError(f"{label} contracts must be an array of nonempty strings")
    missing = [contract for contract in required if contract not in supported]
    if missing:
        raise ValueError(f"Unsupported required contracts: {', '.join(missing)}")


def _index(items: Any, key: str, label: str) -> dict[str, Any]:
    if not isinstance(items, list):
        raise TypeError(f"{label} must be an array")
    result = {}
    for item in items:
        identifier = item.get(key) if isinstance(item, dict) else None
        if not isinstance(identifier, str) or not identifier.strip() or identifier in result:
            raise ValueError(f"{label}: missing or duplicate {key}")
        result[identifier] = item
    return result


def adapt_listening_passes(*, passes: list[dict], participants: list[dict],
                           bindings: list[dict], ensemble: dict | None = None) -> dict:
    """Adapt validated AKOUO input, preserve source, and validate Earworm output."""
    pass_index = _index(passes, "id", "passes")
    participant_index = _index(participants, "id", "participants")
    binding_index = _index(bindings, "pass_id", "bindings")
    _index(bindings, "listening_id", "bindings")
    if set(binding_index) != set(pass_index):
        raise ValueError("bindings must map every pass exactly once")

    def mapped(identifier: str) -> str:
        if identifier not in binding_index:
            raise ValueError(f"Unresolved listening pass: {identifier}")
        return binding_index[identifier]["listening_id"]

    listenings = []
    for listening_pass in passes:
        participant = participant_index.get(listening_pass.get("listener_id"))
        if participant is None:
            raise ValueError(f"Unresolved participant: {listening_pass.get('listener_id')}")
        for key in ("route", "decision_refs", "influenced_by"):
            if not isinstance(listening_pass.get(key), list):
                raise ValueError(f"pass.{key} must be an array")
        binding = binding_index[listening_pass["id"]]
        influences = []
        for influence in listening_pass["influenced_by"]:
            if influence.get("pass_id") == listening_pass["id"]:
                raise ValueError("A pass cannot influence itself")
            influences.append({"listening_id": mapped(influence.get("pass_id")), "effect": influence.get("effect")})
        listening = {
            "listening_id": mapped(listening_pass["id"]), "listener_id": participant["id"],
            "listener_type": participant.get("type"), "created_at": listening_pass.get("started_at"),
            "report_namespace": binding.get("report_namespace"), "contract": binding.get("contract"),
            "route": deepcopy(listening_pass.get("route")), "listening_pass_ref": listening_pass["id"],
            "route_decision_refs": deepcopy(listening_pass.get("decision_refs")), "influenced_by": influences,
        }
        if listening_pass.get("revision_of") is not None:
            mapped(listening_pass["revision_of"])
        errors = _errors(_LISTENING, listening)
        if errors:
            raise ValueError("; ".join(errors))
        listenings.append(listening)
    stored_ensemble = None
    if ensemble is not None:
        for key in ("participant_ids", "listening_pass_ids", "influence_edges"):
            if not isinstance(ensemble.get(key), list):
                raise ValueError(f"ensemble.{key} must be an array")
        members, actors = set(ensemble["listening_pass_ids"]), set(ensemble["participant_ids"])
        if len(actors) != len(ensemble["participant_ids"]) or len(actors) < 2 or not actors <= participant_index.keys():
            raise ValueError("Invalid ensemble participants")
        for identifier in members:
            mapped(identifier)
        if actors != {pass_index[identifier]["listener_id"] for identifier in members}:
            raise ValueError("Ensemble participants must match the listeners of its passes")
        edges = []
        for edge in ensemble["influence_edges"]:
            source, target = edge.get("from_pass_id"), edge.get("to_pass_id")
            if source not in members or target not in members or source == target:
                raise ValueError("Ensemble influence must connect two distinct member passes")
            if not any(item.get("pass_id") == source and item.get("effect") == edge.get("effect")
                       for item in pass_index[target]["influenced_by"]):
                raise ValueError("Ensemble influence must match its target pass attribution")
            edges.append({"from_listening_id": mapped(source), "to_listening_id": mapped(target), "effect": edge.get("effect")})
        stored_ensemble = {
            "id": ensemble.get("id"), "kind": ensemble.get("kind"),
            "listening_ids": [mapped(identifier) for identifier in ensemble["listening_pass_ids"]],
            "influence_edges": edges, "permissions_preserved": ensemble.get("permissions_preserved"),
            "disagreements_preserved": ensemble.get("disagreements_preserved"), "dissolution_rule": ensemble.get("dissolution_rule"),
        }
        for identifier in members:
            for influence in pass_index[identifier]["influenced_by"]:
                if influence["pass_id"] in members and not any(
                    edge.get("from_pass_id") == influence["pass_id"] and edge.get("to_pass_id") == identifier
                    and edge.get("effect") == influence["effect"] for edge in ensemble["influence_edges"]
                ):
                    raise ValueError("Ensemble must retain every influence between its member passes")
        errors = _errors(_ENSEMBLE, stored_ensemble)
        if errors:
            raise ValueError("; ".join(errors))
    return {
        "listenings": listenings, "ensemble": stored_ensemble,
        "pass_to_listening": {item["pass_id"]: item["listening_id"] for item in bindings},
        "source": deepcopy({"passes": passes, "participants": participants, "ensemble": ensemble}),
    }
