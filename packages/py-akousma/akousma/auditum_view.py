"""Permission-aware local auditum views, reusing retained forgetting receipts."""
from __future__ import annotations

from copy import deepcopy
from .listening_context import _instant
from .listening_contracts import assert_supported_contracts

AUDITUM_VIEW_CONTRACT = "earworm/auditum-view/v1"
FORGETTING_RECEIPT_CONTRACT = "earworm/forgetting-receipt/v1"
_FLAGS = ("record_deleted", "audio_deletion_requested", "audio_deleted", "shared_audio_preserved")


def _identifier(value):
    return isinstance(value, str) and bool(value.strip())


def forgetting_receipt_view(receipt, record_id):
    """Allowlist metadata; omit arbitrary actor, reason, recovery and extension text."""
    if (not _identifier(record_id) or not isinstance(receipt, dict)
            or receipt.get("contract") != FORGETTING_RECEIPT_CONTRACT
            or receipt.get("akousma_id") != record_id or not _identifier(receipt.get("receipt_id"))
            or any(type(receipt.get(key)) is not bool for key in _FLAGS)
            or receipt["record_deleted"] is not True):
        raise ValueError("Invalid forgetting receipt identity, contract or deletion flags")
    _instant(receipt.get("created_at"))
    if ((receipt["audio_deleted"] or receipt["shared_audio_preserved"]) and not receipt["audio_deletion_requested"]
            or receipt["audio_deleted"] and receipt["shared_audio_preserved"]):
        raise ValueError("Inconsistent forgetting receipt audio outcome")
    return {key: receipt[key] for key in ("contract", "receipt_id", "akousma_id", "created_at", *_FLAGS)}


def _references(record):
    lineage = record.get("lineage", {})
    auditum = record.get("auditum", {})
    refs = list(lineage.get("parent_akousma_ids", []))
    refs.extend(r.get("target_akousma_id") for r in lineage.get("relations", []))
    refs.append(auditum.get("revision", {}).get("revises_akousma_id"))
    if record["schema_version"] in {"1.7.0", "1.8.0"}:
        refs.append(auditum.get("appeal", {}).get("legacy_source", {}).get("record_ref"))
        decision = record.get("extensions", {}).get("earworm_generation_decision")
        if decision:
            refs.append(decision["generation_ref"])
            refs.extend(r["record_ref"] for r in decision["subsequent_listenings"])
        for relation in lineage.get("relations", []):
            refs.extend(r["record_ref"] for r in relation.get("criterion", {}).get("descriptor_refs", []))
    return sorted({ref for ref in refs if _identifier(ref) and ref != record["akousma_id"]})


def auditum_view(record_id, *, read_record, read_receipt, can_read, supported_contracts):
    """One-hop view. Permission runs before lookups; resolver failures propagate."""
    from . import validation_errors
    assert_supported_contracts([AUDITUM_VIEW_CONTRACT, FORGETTING_RECEIPT_CONTRACT], supported_contracts)
    if not _identifier(record_id) or not all(callable(fn) for fn in (read_record, read_receipt, can_read)):
        raise TypeError("Record ID, record/receipt resolvers and an explicit permission callback are required")

    def resolve(identifier):
        permitted = can_read(identifier)
        if type(permitted) is not bool:
            raise TypeError("can_read must return a boolean")
        if not permitted:
            return {"record_ref": identifier, "state": "withheld"}, None
        record = read_record(identifier)
        if record is not None:
            if validation_errors(record) or record["akousma_id"] != identifier:
                raise ValueError("Invalid or mismatched resolved record")
            return {"record_ref": identifier, "state": "available"}, record
        receipt = read_receipt(identifier)
        return ({"record_ref": identifier, "state": "unavailable"} if receipt is None else
                {"record_ref": identifier, "state": "forgotten", "receipt": forgetting_receipt_view(receipt, identifier)}), None

    entry, record = resolve(record_id)
    view = {"contract": AUDITUM_VIEW_CONTRACT, **entry}
    if record is not None:
        view.update(auditum=deepcopy(record.get("auditum")), references=[resolve(ref)[0] for ref in _references(record)])
    return view
