"""Additive evidence/deployment contracts; existing records are never rewritten."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from jsonschema import Draft7Validator

_ROOT = Path(__file__).parent


def contract_errors(name, value):
    if name not in {"embedding-space", "analysis-evidence", "model-deployment"}:
        raise ValueError("unknown ecology contract")
    try:
        json.dumps(value, allow_nan=False)
    except (ValueError, TypeError):
        return ["value must contain finite JSON data"]
    validator = Draft7Validator(json.loads((_ROOT / f"{name}.schema.json").read_text()))
    errors = [f"{list(e.path)}: {e.message}" for e in validator.iter_errors(value)]
    if not errors and name == "analysis-evidence":
        view = value["view"]
        if view["end_seconds"] <= view["start_seconds"]:
            errors.append("analysis view must have positive duration")
    return errors


def deployment_errors(value, *, adapters, capabilities):
    errors = contract_errors("model-deployment", value)
    if errors:
        return errors
    if value["adapter"] not in adapters:
        errors.append("adapter is not registered by this owner")
    if not set(value["capabilities"]).issubset(capabilities):
        errors.append("unsupported capability")
    if not value["enabled"] or not value["provisioned"]:
        errors.append("deployment must be enabled and provisioned")
    if value["measured_peak_memory_mib"] is None:
        errors.append("deployment memory profile has not been measured")
    for field in ("license_review", "validation_receipt"):
        if value[field].strip().lower() in {
            "unknown",
            "pending",
            "pin_required",
            "required",
        }:
            errors.append(f"{field} is unresolved")
    return errors


def embedding(value):
    """Return (canonical space identity, vector), or None for unsafe/legacy data."""
    if not isinstance(value, dict) or contract_errors(
        "embedding-space", value.get("space")
    ):
        return None
    vector = value.get("vector")
    if not isinstance(vector, list) or len(vector) != value["space"]["dimensions"]:
        return None
    if any(
        isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v)
        for v in vector
    ):
        return None
    identity = hashlib.sha256(
        json.dumps(value["space"], sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return identity, [float(v) for v in vector]
