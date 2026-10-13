"""Offline representation contracts. Validation never fetches or adopts content."""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft7Validator
from referencing import Registry, Resource

from .listening_contracts import _nonfinite, assert_supported_contracts

REPRESENTATION_SCHEMA_VERSION = "1.9.0"
REPRESENTATION_CONTRACTS = (
    "earworm/representation/v1", "earworm/representation-access/v1",
    "earworm/representation-output/v1", "earworm/representation-record/v1",
    "earworm/akousma/v1.9",
)
_NAMES = ("representation", "representation-access", "representation-output",
          "representation-record", "representation-measurement", "akousma-1.9")
_TEXT_FORMS = {"text", "notation", "data", "morse", "glyphs", "code"}


@lru_cache(maxsize=1)
def _validators():
    schemas = {name: json.loads(Path(__file__).with_name(name + ".schema.json").read_text())
               for name in _NAMES}
    registry = Registry().with_resources((s["$id"], Resource.from_contents(s))
                                         for s in schemas.values())
    return {name: Draft7Validator(s, registry=registry) for name, s in schemas.items()}


def _shape(name, value):
    if _nonfinite(value):
        return ["Nonfinite representation value"]
    return [f"{'/'.join(map(str, e.path)) or '<root>'}: {e.message}"
            for e in _validators()[name].iter_errors(value)]


def representation_errors(value: Any) -> list[str]:
    errors = _shape("representation", value)
    if errors:
        return errors
    artifact = value["artifact"]
    if value["form"] in _TEXT_FORMS and "encoding" not in value:
        errors.append("Textual representation requires an explicit encoding")
    if "inline_text" in artifact:
        if artifact["state"] != "retained" or value["form"] not in _TEXT_FORMS or value.get("encoding") != "utf-8":
            errors.append("Inline text requires a retained UTF-8 textual representation")
        try:
            content = artifact["inline_text"].encode("utf-8")
            if sha256(content).hexdigest() != artifact.get("sha256") or len(content) != artifact.get("byte_count"):
                errors.append("Inline text digest or byte count mismatch")
        except UnicodeEncodeError:
            errors.append("Inline text contains an unpaired Unicode surrogate")
    if value["preservation"]["layout"] == "preserved" and value["preservation"]["losses"]:
        errors.append("Preserved layout cannot declare layout losses")
    if value["preservation"]["layout"] == "transformed" and value["origin"]["kind"] != "transformed":
        errors.append("Transformed layout requires a declared transformation origin")
    for basis in value["time_basis"]:
        if basis["kind"] == "unknown" and "reason" not in basis:
            errors.append("Unknown time basis requires a reason")
        if "extent" in basis:
            if "unit" not in basis or basis["extent"]["start"] > basis["extent"]["end"]:
                errors.append("Time extent requires units and ordered bounds")
        if basis["kind"] in {"source_event", "capture", "execution"} and "clock_ref" not in basis:
            errors.append("Event time requires an explicit clock")
    return errors


def representation_measurement_errors(value: Any) -> list[str]:
    return _shape("representation-measurement", value)


def representation_record_errors(value: Any) -> list[str]:
    """Validate the closed declared scope, not attention or the truth of prose."""
    errors = _shape("representation-record", value)
    if errors:
        return errors
    reps = {r["representation_id"]: r for r in value["representations"]}
    accesses = {a["access_id"]: a for a in value["accesses"]}
    bindings = {b["binding_id"]: b for b in value["binding_refs"]}
    identifiers = [r["representation_id"] for r in value["representations"]]
    identifiers += [a["access_id"] for a in value["accesses"]]
    identifiers += [r["relation_id"] for r in value["relations"]]
    identifiers += [o["output_id"] for o in value["outputs"]]
    identifiers += [b["binding_id"] for b in value["binding_refs"]]
    if len(set(identifiers)) != len(identifiers):
        errors.append("Duplicate representation-scope identity")
    for rep in reps.values():
        errors.extend(representation_errors(rep))
    graph = {key: [] for key in reps}
    for relation in value["relations"]:
        child, parent = relation["from_ref"], relation["to_ref"]
        if child not in reps or parent not in reps or child == parent:
            errors.append("Relation requires two distinct resolved representations")
            continue
        graph[child].append(parent)
        if relation["kind"] == "transformed_from":
            if "method_ref" not in relation or "losses" not in relation:
                errors.append("Transformation requires a method and declared losses")
            if reps[child]["origin"]["kind"] != "transformed" or parent not in reps[child]["origin"]["source_refs"]:
                errors.append("Transformation origin must identify its parent representation")
    # Iterative traversal handles long chains without exhausting the Python stack.
    incoming = {key: 0 for key in reps}
    for parents in graph.values():
        for parent in parents:
            incoming[parent] += 1
    ready = [key for key, count in incoming.items() if count == 0]
    visited = 0
    while ready:
        key = ready.pop()
        visited += 1
        for parent in graph[key]:
            incoming[parent] -= 1
            if incoming[parent] == 0:
                ready.append(parent)
    if visited != len(reps):
        errors.append("Cyclic representation lineage")
    for rep in reps.values():
        if rep["origin"]["kind"] == "transformed" and not any(
            r["kind"] == "transformed_from" and r["from_ref"] == rep["representation_id"]
            for r in value["relations"]
        ):
            errors.append("Transformed representation requires explicit lineage")
    for binding in bindings.values():
        document = reps.get(binding["document_representation_ref"])
        if not document or document["artifact"].get("sha256") != binding["document_sha256"]:
            errors.append("Binding must identify the complete document digest")
        if binding["scope"]["kind"] == "invocation" and binding["scope"]["ref"] != value["operation_ref"]:
            errors.append("Invocation binding must identify this operation")
    available = []
    for access in accesses.values():
        source = reps.get(access["representation_ref"])
        received = reps.get(access.get("received_representation_ref"))
        coverage = access["coverage"]
        if access["operation_ref"] != value["operation_ref"] or source is None:
            errors.append("Access operation or source is unresolved")
        if access["status"] == "available":
            available.append(access)
            if received is None or coverage["kind"] == "none":
                errors.append("Available access requires actual supplied material")
            elif received["artifact"]["state"] in {"withheld", "unknown"}:
                errors.append("Available access cannot receive withheld or unknown material")
            elif "sha256" not in received["artifact"] or "byte_count" not in received["artifact"]:
                errors.append("Available access requires exact received-byte identity")
            if coverage["kind"] == "full" and access.get("received_representation_ref") != access["representation_ref"]:
                errors.append("Full access must name the original representation")
            if coverage["kind"] == "partial":
                if not coverage["ranges"] or coverage["unit"] == "unknown" or received is source:
                    errors.append("Partial access requires ranges and a distinct derivative")
                if not any(r["kind"] == "transformed_from" and r["from_ref"] == access.get("received_representation_ref")
                           and r["to_ref"] == access["representation_ref"] for r in value["relations"]):
                    errors.append("Partial access requires a declared transformation")
        elif access.get("received_representation_ref") or coverage["kind"] != "none" or coverage["ranges"] or "reason" not in access:
            errors.append("Unavailable access must declare none and its reason")
        previous = -1
        for interval in coverage["ranges"]:
            if interval["start"] >= interval["end"] or interval["start"] < previous:
                errors.append("Coverage ranges must be ordered, nonempty and disjoint")
            previous = interval["end"]
            if source and coverage["unit"] == "byte" and interval["end"] > source["artifact"].get("byte_count", -1):
                errors.append("Coverage exceeds the declared source bytes")
        if coverage["kind"] == "full" and (coverage["omissions"] or (coverage["ranges"] and (
            len(coverage["ranges"]) != 1 or coverage["ranges"][0]["start"] != 0 or
            (source and coverage["unit"] == "byte" and coverage["ranges"][0]["end"] != source["artifact"].get("byte_count"))
        ))):
            errors.append("Full access cannot omit or truncate material")
        if access["role"] == "instruction":
            binding = bindings.get(access.get("binding_ref"))
            if not binding or binding["document_representation_ref"] != access["representation_ref"]:
                errors.append("Instruction role requires its explicit document binding")
        elif "binding_ref" in access:
            errors.append("A source or context cannot activate an instruction binding")
    for output in value["outputs"]:
        rep = reps.get(output["representation_ref"])
        if output["operation_ref"] != value["operation_ref"] or rep is None:
            errors.append("Output operation or representation is unresolved")
        inputs = [accesses.get(key) for key in output["input_access_refs"]]
        if any(a is None or a["status"] != "available" for a in inputs):
            errors.append("Output inputs must resolve to available accesses")
        if any(a and a.get("received_representation_ref") == output["representation_ref"] for a in inputs):
            errors.append("Output requires a new representation identity")
        if output["completion"] == "complete" and rep and rep["artifact"]["state"] != "retained":
            errors.append("Complete output requires the retained complete artifact")
        expected = "account_of" if output["kind"] == "account" else "response_to"
        if output["kind"] in {"account", "work"} and not any(
            r["kind"] == expected and r["from_ref"] == output["representation_ref"] and
            any(a and r["to_ref"] == a.get("received_representation_ref") for a in inputs)
            for r in value["relations"]
        ):
            errors.append("Account or work requires its declared source relation")
    status = value["outcome"]["status"]
    if status == "completed" and (not value["outputs"] or any(o["completion"] != "complete" for o in value["outputs"])):
        errors.append("Completed outcome requires complete outputs")
    if status in {"no_response", "refused", "withheld", "missing", "source_only", "pending"} and value["outputs"]:
        errors.append("This outcome cannot carry completed or partial outputs")
    if status == "no_response" and not available:
        errors.append("No-response outcome requires declared available material")
    if status in {"refused", "missing", "source_only"} and available:
        errors.append("A refusal, missing history or source-only record cannot claim material was supplied")
    returned = value.get("return")
    if returned:
        if returned["previous_operation_ref"] == value["operation_ref"]:
            errors.append("A return must identify another operation")
        if not any(a["representation_ref"] == returned["representation_ref"] and
                   a["role"] in {"subject", "score", "work"} for a in available):
            errors.append("Return subject must be an available primary input")
        if returned["context_basis"] == "independent" and returned["context_access_refs"]:
            errors.append("Independent return cannot supply earlier accounts")
        if returned["context_basis"] == "independent" and any(a["role"] == "account" for a in available):
            errors.append("Independent return cannot receive an account as context")
        if returned["context_basis"] in {"informed", "shared_analysis"} and not returned["context_access_refs"]:
            errors.append("Informed or shared return requires declared context")
        for key in returned["context_access_refs"]:
            if key not in accesses or accesses[key]["status"] != "available" or accesses[key]["role"] not in {"account", "context"}:
                errors.append("Return context must resolve to an available account or context")
    return errors


def record_19_errors(record: Any, *, validate_native=None, resolve_object=None) -> list[str]:
    errors = _shape("akousma-1.9", record)
    if errors:
        return errors
    block = record.get("extensions", {}).get("earworm_representation")
    if block is not None:
        errors.extend(representation_record_errors(block))
        if block["record_ref"] != record["akousma_id"]:
            errors.append("Representation block belongs to another record")
    if record.get("record_kind") == "representation_record":
        reserved = set(record.get("extensions", {})) & {
            "earworm_research", "earworm_generation_decision", "earworm_observation",
            "earworm_agent_sector", "earworm_transformation_graph", "oida.spectral", "akouo.agent-native",
            "earworm_listening_access", "earworm_listening_context",
        }
        if reserved or any(key in record for key in ("audio", "auditum", "listening")):
            errors.append("Representation records cannot impersonate legacy audio or auditum paths")
    else:
        from .spectral import record_18_errors
        legacy = deepcopy(record)
        legacy["schema_version"] = "1.8.0"
        legacy.get("extensions", {}).pop("earworm_representation", None)
        errors.extend(record_18_errors(legacy, validate_native=validate_native, resolve_object=resolve_object))
    return errors


def admit_representation_record(value: Any, *, supported_contracts, resolve_artifact=None,
                                validate_binding=None, resolve_operation=None) -> dict:
    """Admit bytes via a host resolver. No IO or policy adoption occurs here."""
    supported = list(supported_contracts) if isinstance(supported_contracts, (list, tuple)) else supported_contracts
    assert_supported_contracts(list(REPRESENTATION_CONTRACTS), supported)
    errors = representation_record_errors(value)
    if errors:
        raise ValueError("; ".join(errors))
    reps = {r["representation_id"]: r for r in value["representations"]}
    required = {a["received_representation_ref"] for a in value["accesses"] if a["status"] == "available"}
    required.update(o["representation_ref"] for o in value["outputs"])
    for key in sorted(required):
        rep = reps[key]
        artifact = rep["artifact"]
        if "inline_text" in artifact:
            content = artifact["inline_text"].encode("utf-8")
        else:
            content = resolve_artifact(deepcopy(rep)) if callable(resolve_artifact) else None
        if not isinstance(content, (bytes, bytearray)) or sha256(content).hexdigest() != artifact.get("sha256") or len(content) != artifact.get("byte_count"):
            errors.append("Supplied artifact bytes are unavailable or mismatched: " + key)
            continue
        if rep.get("encoding") == "utf-8":
            try:
                content.decode("utf-8")
            except UnicodeDecodeError:
                errors.append("Supplied artifact is not valid UTF-8: " + key)
    for access in value["accesses"]:
        if access["role"] == "instruction":
            binding = next(b for b in value["binding_refs"] if b["binding_id"] == access["binding_ref"])
            result = validate_binding(deepcopy(binding), deepcopy(access)) if callable(validate_binding) else None
            if not isinstance(result, list) or any(not isinstance(e, str) for e in result):
                errors.append("Instruction binding has not been validated by its owner")
            else:
                errors.extend(result)
    returned = value.get("return")
    if returned:
        previous = resolve_operation(returned["previous_operation_ref"]) if callable(resolve_operation) else None
        if not isinstance(previous, dict) or previous.get("operation_ref") != returned["previous_operation_ref"]:
            errors.append("Return operation is unresolved by its owner")
        elif returned["kind"] == "original" and previous.get("primary_representation_ref") != returned["representation_ref"]:
            errors.append("Original return must resolve to the previous subject")
        else:
            outputs = previous.get("output_representation_refs", [])
            accounts = previous.get("account_representation_refs", [])
            if not isinstance(outputs, list) or not isinstance(accounts, list) or any(not isinstance(x, str) for x in outputs + accounts):
                errors.append("Return owner references must be arrays of identities")
            elif returned["kind"] == "descendant" and returned["representation_ref"] not in outputs:
                errors.append("Descendant return must resolve to a previous output")
            if isinstance(accounts, list) and returned["context_basis"] == "independent" and any(
                a.get("received_representation_ref") in accounts or a["representation_ref"] in accounts
                for a in value["accesses"] if a["status"] == "available"
            ):
                errors.append("Independent return received a prior account")
    if errors:
        raise ValueError("; ".join(errors))
    return deepcopy(value)
