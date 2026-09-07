"""Explicit unreleased akousma 1.7 / auditum v3 validation and revision adapter."""
from __future__ import annotations
import json
from copy import deepcopy
from typing import Any
from jsonschema import Draft7Validator
from .listening_contracts import _ROOT, _errors, _nonfinite, assert_supported_contracts
from .listening_context import _instant

NEXT_AKOUSMA_SCHEMA_VERSION = "1.7.0"
NEXT_AUDITUM_CONTRACT = "earworm/auditum/v3"
RECORD_EVOLUTION_CONTRACT = "earworm/akousma/v1.7"
_NEXT = Draft7Validator(json.loads((_ROOT / "akousma-1.7.schema.json").read_text()))
_LEGACY = Draft7Validator(json.loads((_ROOT / "akousma.schema.json").read_text()))


def next_record_errors(record: Any) -> list[str]:
    if _nonfinite(record):
        return ["record must contain only finite JSON numbers"]
    errors = _errors(_NEXT, record)
    if errors:
        return errors
    errors.extend(_auditum_reference_errors(record))
    from .observation_accounts import observation_binding_errors
    errors.extend(observation_binding_errors(record))
    from .agent_sectors import agent_sector_binding_errors
    errors.extend(agent_sector_binding_errors(record))
    from .graph_records import graph_record_errors
    errors.extend(graph_record_errors(record))
    typed = [relation for relation in record["lineage"].get("relations", []) if relation.get("contract") == "earworm/relations/v1"]
    ids = set()
    for relation in typed:
        if relation["relation_id"] in ids:
            errors.append("relation_id is duplicated")
        ids.add(relation["relation_id"])
        if relation["target_akousma_id"] == record["akousma_id"]:
            errors.append("typed relation cannot target its own record")
        if relation["type"] != "similar_by" and "criterion" in relation:
            errors.append("criterion belongs only to similar_by")
        if relation["type"] == "similar_by" and relation["target_akousma_id"] not in relation["criterion"]["input_refs"]:
            errors.append("similarity criterion must identify the target input")
    appeal = record.get("auditum", {}).get("appeal")
    if appeal and "resolution" in appeal and appeal["status"] != "resolved":
        errors.append("appeal resolution requires resolved status")
    research = record.get("extensions", {}).get("earworm_research")
    decision = record.get("extensions", {}).get("earworm_generation_decision")
    if research:
        if record.get("record_kind") != "research_proposal":
            errors.append("research extension requires research_proposal record_kind")
        for ref in research["proposed_relation_refs"]:
            if ref not in ids:
                errors.append("unresolved proposed relation")
    if decision:
        if record.get("record_kind") != "generation_decision":
            errors.append("decision extension requires generation_decision record_kind")
        if decision["generation_ref"] not in decision["input_refs"]:
            errors.append("generation must remain an explicit decision input")
        if not any(relation["type"] == "decision_on" and relation["target_akousma_id"] == decision["generation_ref"] for relation in typed):
            errors.append("decision_on relation must identify the generation")
        pairs = [(item["record_ref"], item["listening_ref"]) for item in decision["subsequent_listenings"]]
        if len(set(pairs)) != len(pairs):
            errors.append("subsequent listening reference is duplicated")
        for item in decision["subsequent_listenings"]:
            if item["record_ref"] not in decision["input_refs"]:
                errors.append("subsequent listening record must remain an explicit input")
        if decision["outcome"] in ("keep", "discard") and (decision["next_job"]["status"] != "none" or decision["stop_outcome"] == "continue"):
            errors.append("keep/discard cannot schedule a next job")
        if decision["stop_outcome"] == "continue" and decision["next_job"]["status"] != "planned":
            errors.append("continue requires an explicit planned next job")
        if decision["stop_outcome"] != "continue" and decision["next_job"]["status"] != "none":
            errors.append("stop/defer cannot schedule a next job")
    return errors


def next_record_reference_errors(record: dict, records: list[dict]) -> list[str]:
    """Check record-valued references in an explicit scope, without network IO."""
    errors = next_record_errors(record)
    if errors:
        return errors
    if not isinstance(records, list) or any(not isinstance(item, dict) or not isinstance(item.get("akousma_id"), str) for item in records):
        return ["reference scope must contain identified records"]
    scope = {item["akousma_id"]: item for item in records}
    if len(scope) != len(records):
        return ["reference scope has duplicate record identities"]
    for source in scope.values():
        problems = next_record_errors(source) if source.get("schema_version") == NEXT_AKOUSMA_SCHEMA_VERSION else _errors(_LEGACY, source)
        if problems or _nonfinite(source):
            errors.append(f"invalid referenced record: {source['akousma_id']}")
    if errors:
        return errors
    graph = record.get("extensions", {}).get("earworm_transformation_graph")
    if graph and graph["revision"] > 1:
        previous = scope.get(record.get("auditum", {}).get("revision", {}).get("revises_akousma_id"))
        if previous is None:
            errors.append("Unresolved graph revision parent")
        else:
            from .graph_records import graph_revision_errors
            errors.extend(graph_revision_errors(record, previous))
    legacy = record.get("auditum", {}).get("appeal", {}).get("legacy_source")
    if legacy:
        payload = scope.get(legacy["record_ref"], {}).get("extensions", {}).get("oida")
        if not isinstance(payload, dict) or "appeal" not in payload:
            errors.append("unresolved legacy appeal source")
        elif not _same_json(payload["appeal"], legacy["payload"]):
            errors.append("legacy appeal payload differs from its retained source")
    for relation in record["lineage"].get("relations", []):
        if relation.get("contract") == "earworm/relations/v1" and relation["target_akousma_id"] not in scope:
            errors.append(f"unresolved relation target: {relation['target_akousma_id']}")
    from .agent_sectors import descriptor_relation_errors
    errors.extend(descriptor_relation_errors(record,scope))
    decision = record.get("extensions", {}).get("earworm_generation_decision")
    if not decision:
        return errors
    generation = scope.get(decision["generation_ref"])
    if not generation or generation.get("provenance", {}).get("source_type") != "generated":
        errors.append("generation_ref must resolve to a generated record")
    for ref in decision["subsequent_listenings"]:
        source = scope.get(ref["record_ref"], {})
        listening = next((item for item in source.get("auditum", {}).get("listenings", []) if item.get("listening_id") == ref["listening_ref"]), None)
        if not listening:
            errors.append("unresolved subsequent listening")
            continue
        try:
            if generation and _instant(listening.get("created_at")) < _instant(generation.get("created_at")):
                errors.append("listening precedes generation")
            if _instant(record["created_at"]) < _instant(listening.get("created_at")):
                errors.append("decision precedes its listening input")
        except (ValueError, TypeError):
            errors.append("cannot establish generation/listening/decision chronology")
    return errors


def promote_legacy_appeal(record: dict, options: dict) -> dict:
    """Return a negotiated revision with opaque legacy payload; never mutate input."""
    assert_supported_contracts([RECORD_EVOLUTION_CONTRACT, NEXT_AUDITUM_CONTRACT], options.get("supported_contracts"))
    for key in ("akousma_id", "revision_id", "created_at", "appeal_id", "recorded_by", "reason"):
        if not isinstance(options.get(key), str) or not options[key].strip():
            raise ValueError(f"Missing promotion option: {key}")
    if options["akousma_id"] == record["akousma_id"]:
        raise ValueError("Promotion requires a fresh record id")
    errors = next_record_errors(record) if record.get("schema_version") == NEXT_AKOUSMA_SCHEMA_VERSION else _errors(_LEGACY, record)
    if errors:
        raise ValueError("; ".join(errors))
    if not record.get("auditum", {}).get("route_decisions"):
        raise ValueError("An attributable auditum with route decisions is required")
    if record["auditum"].get("appeal"):
        raise ValueError("A promoted appeal already exists; use an explicit revision")
    oida = record.get("extensions", {}).get("oida")
    if not isinstance(oida, dict) or "appeal" not in oida:
        raise ValueError("No retained extensions.oida.appeal payload")
    if _instant(options["created_at"]) < _instant(record["created_at"]):
        raise ValueError("Revision precedes its source record")
    result = deepcopy(record)
    result.update(akousma_id=options["akousma_id"], created_at=options["created_at"], schema_version=NEXT_AKOUSMA_SCHEMA_VERSION)
    result["auditum"]["contract"] = NEXT_AUDITUM_CONTRACT
    result["auditum"]["revision"] = {"revision_id": options["revision_id"], "revises_akousma_id": record["akousma_id"], "reason": options["reason"],
        "changes": ["Promoted retained appeal into negotiated auditum.appeal."], "created_at": options["created_at"]}
    result["auditum"]["appeal"] = {"contract": "earworm/appeal/v1", "appeal_id": options["appeal_id"], "recorded_by": options["recorded_by"],
        "subject_refs": deepcopy(options.get("subject_refs")), "reason": options["reason"], "status": "unreviewed", "evidence_refs": [record["akousma_id"]],
        "legacy_source": {"record_ref": record["akousma_id"], "path": "/extensions/oida/appeal", "payload": deepcopy(oida["appeal"])}}
    errors = next_record_errors(result)
    if errors:
        raise ValueError("; ".join(errors))
    return result


def _same_json(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(_same_json(left[key], right[key]) for key in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(_same_json(a, b) for a, b in zip(left, right))
    return left == right


def _auditum_reference_errors(record: dict) -> list[str]:
    block = record.get("auditum")
    if not block:
        return []
    errors = []
    listenings = {item["listening_id"] for item in block["listenings"]}
    if not block.get("route_decisions") and record.get("record_kind") != "transformation_graph":
        return ["Revision-only auditum belongs to a graph artifact"]
    decisions = {item["decision_id"] for item in block["route_decisions"]}
    if len(listenings) != len(block["listenings"]) or len(decisions) != len(block["route_decisions"]):
        errors.append("duplicate auditum listening or decision identity")
    for listening in block["listenings"]:
        for ref in listening.get("route_decision_refs", []):
            if ref not in decisions:
                errors.append("unresolved listening route decision")
        for influence in listening.get("influenced_by", []):
            if influence["listening_id"] not in listenings or influence["listening_id"] == listening["listening_id"]:
                errors.append("invalid listening influence reference")
    for item in block["route_decisions"] + block["honest_absences"]:
        if item.get("listening_id") is not None and item["listening_id"] not in listenings:
            errors.append("unresolved attributable listening")
    for disagreement in block["disagreements"]:
        if not set(disagreement["listening_ids"]) <= listenings:
            errors.append("unresolved disagreement listening")
        if any(position["listening_id"] not in disagreement["listening_ids"] for position in disagreement["positions"]):
            errors.append("unattributable disagreement position")
        if disagreement["status"] == "resolved" and not (disagreement.get("resolution_note") or "").strip():
            errors.append("resolved disagreement needs a resolution note")
    ensemble = block.get("ensemble")
    if ensemble:
        members = set(ensemble["listening_ids"])
        if not members <= listenings:
            errors.append("unresolved ensemble member")
        for edge in ensemble["influence_edges"]:
            if edge["from_listening_id"] not in members or edge["to_listening_id"] not in members or edge["from_listening_id"] == edge["to_listening_id"]:
                errors.append("invalid ensemble influence reference")
    if not record.get("record_kind") and not block["listenings"] and not any(item["gate"] in ("input", "capture") and item["outcome"] in ("pause", "defer", "abstain", "refuse", "withhold") for item in block["route_decisions"]):
        errors.append("empty listening account requires a pre-capture stop")
    if block.get("revision", {}).get("revises_akousma_id") == record["akousma_id"]:
        errors.append("revision must reference a different record")
    return errors
