"""Record-bound listening context and independent claim validity/retention."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from jsonschema import Draft7Validator
from referencing import Registry, Resource

from .listening_contracts import _ROOT, _errors, _nonfinite, listening_access_errors

LISTENING_CONTEXT_CONTRACT = "earworm/listening-context/v1"
_SCHEMA = json.loads((_ROOT / "listening-context.schema.json").read_text())
_SCHEMAS = [json.loads(path.read_text()) for path in _ROOT.glob("*.schema.json")]
_REGISTRY = Registry().with_resources((schema["$id"], Resource.from_contents(schema)) for schema in _SCHEMAS)
_CONTEXT = Draft7Validator(_SCHEMA, registry=_REGISTRY)
_CLAIM = Draft7Validator(_SCHEMA["properties"]["claims"]["items"])


def _instant(value: Any) -> datetime:
    if not isinstance(value, str) or not re.fullmatch(r"[1-9]\d{3}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z", value):
        raise ValueError("Expected a UTC timestamp YYYY-MM-DDTHH:mm:ss[.SSS]Z")
    return datetime.fromisoformat(value[:-1]).replace(tzinfo=timezone.utc)


def _claim_errors(claim: Any) -> list[str]:
    errors = _errors(_CLAIM, claim)
    if errors:
        return errors
    try:
        if claim["validity"]["status"] != "unknown":
            _instant(claim["validity"]["issued_at"])
        if claim["validity"]["status"] == "expires" and _instant(claim["validity"]["expires_at"]) <= _instant(claim["validity"]["issued_at"]):
            errors.append("claim expiry must follow issuance")
        if claim["retention"]["status"] == "review_after":
            _instant(claim["retention"]["review_after"])
    except ValueError as error:
        errors.append(str(error))
    return errors


def listening_context_errors(value: Any, record: dict) -> list[str]:
    """Validate record-local references. External reference resolution belongs to the host."""
    if _nonfinite(value):
        return ["numbers must be finite JSON numbers"]
    errors = _errors(_CONTEXT, value)
    if errors:
        return errors
    auditum = record.get("auditum") if isinstance(record, dict) else None
    listenings = auditum.get("listenings") if isinstance(auditum, dict) else None
    if not isinstance(listenings, list):
        return ["record.auditum.listenings is required for reference validation"]
    if any(not isinstance(item, dict) or not isinstance(item.get("listening_id"), str) or not isinstance(item.get("contract"), str) for item in listenings):
        return ["invalid record listening reference"]
    listeners = {item["listening_id"]: item for item in listenings}
    extensions = record.get("extensions", {})
    declarations = list(value.get("access_declarations", []))
    if isinstance(extensions, dict) and "earworm_listening_access" in extensions:
        declarations.insert(0, extensions["earworm_listening_access"])
    access_by_id = {}
    for declaration in declarations:
        if listening_access_errors(declaration):
            errors.append("record has an invalid listening access declaration")
            continue
        if declaration["declaration_id"] in access_by_id:
            errors.append("access declaration id is duplicated")
        access_by_id[declaration["declaration_id"]] = declaration
    seen, rendering_ids = set(), set()
    for context in value["contexts"]:
        listening = listeners.get(context["listening_ref"])
        access = access_by_id.get(context["access_declaration_ref"])
        if listening is None or context["listening_ref"] in seen:
            errors.append("context listening_ref is missing or duplicated")
        seen.add(context["listening_ref"])
        if not isinstance(access, dict) or context["access_declaration_ref"] != access.get("declaration_id"):
            errors.append("unresolved access_declaration_ref")
        if not isinstance(access, dict) or context["subject_ref"] != access.get("subject_ref"):
            errors.append("context subject does not match its access declaration")
        if listening is not None and context["report"]["contract"] != listening["contract"]:
            errors.append("report contract does not match its listening")
        recipients = [recipient["id"] for recipient in context["recipients"]]
        if len(set(recipients)) != len(recipients):
            errors.append("recipient id is duplicated")
        local_renderings = set()
        for rendering in context["renderings"]:
            if rendering["rendering_id"] in rendering_ids:
                errors.append("rendering_id is duplicated")
            rendering_ids.add(rendering["rendering_id"])
            local_renderings.add(rendering["rendering_id"])
            if rendering["source_ref"] == rendering["output_ref"]:
                errors.append("rendering must identify a distinct output")
        human = context["report"]["human_rendering"]
        if human["status"] == "available" and not set(human["rendering_refs"]) <= local_renderings:
            errors.append("human rendering reference is unresolved in this context")
    if len(seen) != len(listeners) or len(listenings) != len(listeners):
        errors.append("contexts must cover each unique record listening exactly once")
    claims = set()
    for claim in value["claims"]:
        if claim["claim_ref"] in claims:
            errors.append("claim_ref is duplicated")
        claims.add(claim["claim_ref"])
        if claim["listening_ref"] not in seen:
            errors.append("claim listening_ref is unresolved")
        errors.extend(_claim_errors(claim))
    return errors


def claim_validity_at(claim: dict, now: str) -> str:
    """Evaluate declared currency, not truth, retention, or permission to act."""
    errors = _claim_errors(claim)
    if errors:
        raise ValueError("; ".join(errors))
    instant = _instant(now)
    validity = claim["validity"]
    if validity["status"] == "unknown":
        return "unknown"
    if instant < _instant(validity["issued_at"]):
        return "not_yet_valid"
    if validity["status"] == "expires" and instant >= _instant(validity["expires_at"]):
        return "expired"
    return "current"


def claim_retention_at(claim: dict, now: str) -> str:
    """Signal policy review only. Never delete or create a forgetting receipt."""
    errors = _claim_errors(claim)
    if errors:
        raise ValueError("; ".join(errors))
    instant = _instant(now)
    retention = claim["retention"]
    if retention["status"] != "review_after":
        return "policy_required"
    return "review_due" if instant >= _instant(retention["review_after"]) else "review_not_due"
