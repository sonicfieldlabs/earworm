"""Application patch graphs of retained MASA operation receipts; no processing engine."""
from __future__ import annotations

import json
from copy import deepcopy
from jsonschema import Draft7Validator
from .listening_contracts import _ROOT, _errors, _nonfinite, assert_supported_contracts
from .record_evolution import _same_json

TRANSFORMATION_GRAPH_CONTRACT = "earworm/transformation-graph/v1"
_SCHEMA = Draft7Validator(json.loads((_ROOT / "transformation-graph.schema.json").read_text()))
_EFFECTS = {"derive", "transform", "render", "map"}


def _derive(record, nodes, validate_masa, lineage_directions):
    if not callable(validate_masa) or not isinstance(lineage_directions, dict):
        raise TypeError("Use the host's MASA validator and versioned lineageRelationDirections registry")
    errors = validate_masa(deepcopy(record))
    if not isinstance(errors, list) or any(not isinstance(e, str) for e in errors):
        raise TypeError("MASA validator must return error strings")
    if errors:
        raise ValueError("; ".join(errors))
    if (record.get("masaVersion") != "0.2.0" or record.get("history", {}).get("mode") != "embedded"
            or not isinstance(record["history"].get("events"), list)
            or not isinstance(record.get("representations"), list) or not isinstance(record.get("relations"), list)):
        raise ValueError("Graph requires MASA 0.2.0 and embedded operation history")
    reps = {r["id"] for r in record["representations"]}
    by_rep = {n["representation_ref"]: n["node_id"] for n in nodes}
    if (len(by_rep) != len(nodes) or len({n["node_id"] for n in nodes}) != len(nodes) or set(by_rep) != reps):
        raise ValueError("Patch nodes must map every representation exactly once with distinct node IDs")
    receipts = [e for e in record["history"]["events"] if e["effectClass"] in _EFFECTS]
    by_operation = {e["id"]: e for e in receipts}
    if len(by_operation) != len(receipts):
        raise ValueError("Duplicate operation receipt")
    for receipt in receipts:
        if receipt["finalStatus"] != "completed" and receipt["outputs"]:
            raise ValueError("Incomplete operations with outputs are outside this graph scope")
        if receipt["finalStatus"] == "completed" and (not receipt["inputs"] or not receipt["outputs"]
                or any(i not in reps for i in receipt["inputs"] + receipt["outputs"])
                or set(receipt["inputs"]) & set(receipt["outputs"])):
            raise ValueError("Completed transformations require retained input and distinct output representations")
    edges = []
    for relation in record["relations"]:
        receipt = by_operation.get(relation.get("operationRef"))
        if not receipt or receipt["finalStatus"] != "completed" or relation["predicate"] not in lineage_directions:
            continue
        direction = lineage_directions[relation["predicate"]]
        if direction not in ("subject-is-descendant", "object-is-descendant"):
            raise ValueError("Invalid MASA lineage direction")
        parent, child = ((relation["object"], relation["subject"]) if direction == "subject-is-descendant"
                         else (relation["subject"], relation["object"]))
        if parent not in receipt["inputs"] or child not in receipt["outputs"]:
            raise ValueError("Lineage direction disagrees with operation inputs and outputs")
        edges.append(dict(relation_ref=relation["id"], operation_ref=receipt["id"],
                          from_node=by_rep[parent], to_node=by_rep[child]))
    for receipt in (r for r in receipts if r["finalStatus"] == "completed"):
        for output in receipt["outputs"]:
            if not any(e["operation_ref"] == receipt["id"] and e["to_node"] == by_rep[output] for e in edges):
                raise ValueError("Each completed output needs a directed receipt-backed lineage relation")
    return dict(edges=edges, operation_refs=[r["id"] for r in receipts])


def graph_required_contracts(source):
    required = [TRANSFORMATION_GRAPH_CONTRACT, 'masa/0.2.0']
    events = source.get('history', {}).get('events', []) if isinstance(source, dict) and isinstance(source.get('history'), dict) else []
    if isinstance(events, list) and any(isinstance(e, dict) and isinstance(e.get('extensions'), dict) and 'earworm:transposition' in e['extensions'] for e in events):
        required.append('earworm/transposition-recipe/v1')
    return required


def create_transformation_graph(record, options, *, validate_masa, lineage_directions):
    """Preserve one MASA source snapshot; map representations to explicit patch nodes."""
    assert_supported_contracts(graph_required_contracts(record), options.get("supported_contracts"))
    graph = dict(contract=TRANSFORMATION_GRAPH_CONTRACT, graph_id=options.get("graph_id"),
                 revision=options.get("revision"), authored_by=options.get("authored_by"),
                 scope="completed_representation_lineage", source_record=deepcopy(record),
                 nodes=deepcopy(options.get("nodes")), edges=[], operation_refs=[])
    errors = _errors(_SCHEMA, graph)
    if errors or _nonfinite(graph):
        raise ValueError("; ".join(errors) or "Graph requires finite JSON numbers")
    graph.update(_derive(graph["source_record"], graph["nodes"], validate_masa, lineage_directions))
    from .graph_records import transformation_graph_binding_errors
    errors = transformation_graph_binding_errors(graph)
    if errors:
        raise ValueError("; ".join(errors))
    return graph


def transformation_graph_errors(graph, *, validate_masa, lineage_directions):
    """Recompute direction and receipt bindings with the host's actual MASA adapter."""
    if _nonfinite(graph):
        return ["Graph requires finite JSON numbers"]
    from .graph_records import transformation_graph_binding_errors
    errors = transformation_graph_binding_errors(graph)
    if errors:
        return errors
    try:
        expected = _derive(graph["source_record"], graph["nodes"], validate_masa, lineage_directions)
        if not _same_json(expected["edges"], graph["edges"]) or not _same_json(expected["operation_refs"], graph["operation_refs"]):
            errors.append("Graph edges or operation references differ from retained MASA evidence")
    except ValueError as error:
        errors.append(str(error))
    return errors
