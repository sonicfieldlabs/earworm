"""Offline E17 manifest validation; storage, grants and bytes belong to hosts."""

import json
from pathlib import Path
from jsonschema import Draft7Validator
from .listening_contracts import _errors, _nonfinite

_SCHEMA = Draft7Validator(
    json.loads((Path(__file__).parent / "bundle-manifest.schema.json").read_text())
)


def bundle_manifest_errors(manifest):
    if _nonfinite(manifest):
        return ["Manifest must be finite JSON"]
    errors = _errors(_SCHEMA, manifest)
    if errors:
        return errors
    entries = manifest["entries"]
    if len({e["path"] for e in entries}) != len(entries) or len(
        {e["id"] for e in entries}
    ) != len(entries):
        errors.append("Bundle paths and IDs must be unique")
    if manifest["disclosure"] == "public-projection" and any(
        e["kind"] != "metadata-projection" for e in entries
    ):
        errors.append("Public bundles contain only metadata projections")
    if manifest["contract"] == "earworm/agent-sounds/v1" and not any(
        e["kind"] == "audio" and e["recipient_requirements"] for e in entries
    ):
        errors.append("Agent sounds require audio and declared recipient capabilities")
    return errors
