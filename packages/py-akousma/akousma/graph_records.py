"""Protected graph account bindings and source-preserving patch revisions."""
import json
from copy import deepcopy
from jsonschema import Draft7Validator
from .listening_contracts import _ROOT, _errors, _nonfinite, assert_supported_contracts
from .listening_context import _instant
from .record_evolution import _same_json
from .transposition_recipes import transposition_recipe_errors

_SCHEMA = Draft7Validator(json.loads((_ROOT / 'transformation-graph.schema.json').read_text()))
_EFFECTS = {'derive', 'transform', 'render', 'map'}

def _strings(v):
    return isinstance(v, list) and all(isinstance(x, str) and x.strip() for x in v)

def transformation_graph_binding_errors(graph):
    errors = _errors(_SCHEMA, graph)
    if errors or _nonfinite(graph):
        return errors or ['Graph requires finite JSON numbers']
    source = graph['source_record']; history = source.get('history', {})
    reps, events, relations = source.get('representations'), history.get('events') if isinstance(history, dict) else None, source.get('relations')
    if (source.get('masaVersion') != '0.2.0' or not isinstance(history, dict) or history.get('mode') != 'embedded'
            or any(not isinstance(a, list) or any(not isinstance(x, dict) or not isinstance(x.get('id'), str) for x in a) or len({x['id'] for x in a}) != len(a) for a in [reps, events, relations])):
        return ['Malformed graph source identity scope']
    if any(not _strings(e.get('inputs')) or not _strings(e.get('outputs')) or not isinstance(e.get('effectClass'), str) or not isinstance(e.get('finalStatus'), str) for e in events) or any(not _strings([r.get('subject'), r.get('object'), r.get('predicate')]) for r in relations):
        return ['Malformed operation or relation references']
    nodes = {n['node_id']: n['representation_ref'] for n in graph['nodes']}
    if len(nodes) != len(graph['nodes']) or len(set(nodes.values())) != len(reps) or len(nodes) != len(reps) or any(r['id'] not in nodes.values() for r in reps):
        return ['Patch nodes must map each representation exactly once']
    receipts = [e for e in events if e.get('effectClass') in _EFFECTS]
    if graph['operation_refs'] != [e['id'] for e in receipts]:
        errors.append('Operation reference list differs from retained receipts')
    seen = set()
    for edge in graph['edges']:
        receipt = next((e for e in receipts if e['id'] == edge['operation_ref']), None)
        relation = next((r for r in relations if r['id'] == edge['relation_ref']), None)
        parent, child = nodes.get(edge['from_node']), nodes.get(edge['to_node'])
        if (edge['relation_ref'] in seen or not receipt or not relation or relation.get('operationRef') != receipt['id'] or receipt.get('finalStatus') != 'completed'
                or not parent or not child or parent == child or parent not in receipt['inputs'] or child not in receipt['outputs']
                or not ((relation['subject'] == parent and relation['object'] == child) or (relation['subject'] == child and relation['object'] == parent))):
            errors.append('Graph edge does not bind its retained operation and relation')
        seen.add(edge['relation_ref'])
    for receipt in receipts:
        if receipt.get('finalStatus') != 'completed' and receipt['outputs']:
            errors.append('Incomplete operation cannot have graph outputs')
        if receipt.get('finalStatus') == 'completed':
            if not receipt['inputs'] or not receipt['outputs'] or any(not any(r['id'] == ref for r in reps) for ref in receipt['inputs'] + receipt['outputs']) or set(receipt['outputs']) & set(receipt['inputs']):
                errors.append('Transformation requires distinct retained representations')
            for output in receipt['outputs']:
                if not any(e['operation_ref'] == receipt['id'] and nodes.get(e['to_node']) == output for e in graph['edges']):
                    errors.append('Completed output needs a receipt-backed graph edge')
    errors.extend(transposition_recipe_errors(source))
    return errors


def graph_record_errors(record):
    graph = record.get('extensions', {}).get('earworm_transformation_graph')
    if graph is None and 'earworm_transformation_graph' not in record.get('extensions', {}):
        return []
    errors = transformation_graph_binding_errors(graph)
    if errors:
        return errors
    if record.get('record_kind') != 'transformation_graph' or record.get('subject') != graph['graph_id']:
        errors.append('Graph record kind and subject must identify the graph')
    revision = record.get('auditum', {}).get('revision')
    if graph['revision'] == 1 and (revision or record.get('akousma_id') != graph['graph_id']):
        errors.append('Initial graph identity must equal its root record ID and have no revision parent')
    if graph['revision'] > 1 and (not revision or revision.get('revises_akousma_id') == record.get('akousma_id') or revision.get('created_at') != record.get('created_at')):
        errors.append('Graph revision needs an explicit fresh record revision')
    return errors


def graph_revision_errors(record, previous):
    errors = graph_record_errors(record) + graph_record_errors(previous)
    if errors:
        return errors
    current, prior = record.get('extensions', {}).get('earworm_transformation_graph'), previous.get('extensions', {}).get('earworm_transformation_graph')
    if (not current or not prior or record.get('auditum', {}).get('revision', {}).get('revises_akousma_id') != previous.get('akousma_id')
            or current['graph_id'] != prior['graph_id'] or current['revision'] != prior['revision'] + 1):
        return ['Graph revisions must retain their family and advance their explicit parent by one']
    if not _same_json(current['source_record'], prior['source_record']):
        errors.append('Patch revision must preserve the complete imported MASA source')
    try:
        if _instant(record.get('created_at')) < _instant(previous.get('created_at')):
            errors.append('Graph revision predates its parent')
    except (ValueError, TypeError):
        errors.append('Graph revision requires valid UTC timestamps')
    return errors


def create_graph_record(graph, options, *, validate_masa, lineage_directions):
    from .transformation_graph import transformation_graph_errors, graph_required_contracts
    from .record_evolution import next_record_errors
    assert_supported_contracts(['earworm/akousma/v1.7', *graph_required_contracts(graph.get('source_record') if isinstance(graph, dict) else None)], options.get('supported_contracts'))
    errors = transformation_graph_errors(graph, validate_masa=validate_masa, lineage_directions=lineage_directions)
    if errors:
        raise ValueError('; '.join(errors))
    _instant(options.get('created_at'))
    record = dict(akousma_id=graph['graph_id'], schema_version='1.7.0', record_kind='transformation_graph', created_at=options['created_at'], subject=graph['graph_id'],
                  provenance=dict(source_type='unknown', origin='unknown', originating_app=options.get('originating_app'), created_at=options['created_at']),
                  lineage=dict(parent_akousma_ids=[]), extensions=dict(earworm_transformation_graph=deepcopy(graph)))
    errors = next_record_errors(record)
    if errors:
        raise ValueError('; '.join(errors))
    return record


def revise_graph_record(record, options, *, validate_masa, lineage_directions):
    from .record_evolution import next_record_errors
    from .transformation_graph import create_transformation_graph, transformation_graph_errors
    assert_supported_contracts(['earworm/akousma/v1.7', 'earworm/auditum/v3', 'earworm/transformation-graph/v1', 'masa/0.2.0'], options.get('supported_contracts'))
    errors = next_record_errors(record)
    if errors or not record.get('extensions', {}).get('earworm_transformation_graph'):
        raise ValueError('; '.join(errors) or 'Graph record required')
    graph = record['extensions']['earworm_transformation_graph']
    errors = transformation_graph_errors(graph, validate_masa=validate_masa, lineage_directions=lineage_directions)
    if errors:
        raise ValueError('; '.join(errors))
    next_record = deepcopy(record)
    next_record.update(akousma_id=options.get('akousma_id'), created_at=options.get('created_at'))
    next_record['extensions']['earworm_transformation_graph'] = create_transformation_graph(graph['source_record'], dict(graph_id=graph['graph_id'], revision=graph['revision'] + 1,
        authored_by=options.get('authored_by'), nodes=options.get('nodes'), supported_contracts=options['supported_contracts']), validate_masa=validate_masa, lineage_directions=lineage_directions)
    next_record.setdefault('auditum', dict(listenings=[], route_decisions=[], disagreements=[], honest_absences=[], actions=[]))['contract'] = 'earworm/auditum/v3'
    next_record['auditum']['revision'] = dict(revision_id=options.get('revision_id'), revises_akousma_id=record['akousma_id'], reason=options.get('reason'),
        changes=['Revised application patch mapping; retained MASA source unchanged.'], created_at=options.get('created_at'))
    errors = next_record_errors(next_record)
    if not errors:
        errors.extend(graph_revision_errors(next_record, record))
    if errors:
        raise ValueError('; '.join(errors))
    return next_record
