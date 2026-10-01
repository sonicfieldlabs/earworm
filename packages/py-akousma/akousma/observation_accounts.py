"""Unreleased, source-preserving observation accounts and MASA label bindings."""
from __future__ import annotations
import json
from copy import deepcopy
from typing import Any, Callable
from jsonschema import Draft7Validator
from .listening_contracts import _ROOT, _errors, _nonfinite, assert_supported_contracts, listening_access_errors
from .listening_context import listening_context_errors, _instant
from .record_evolution import next_record_errors, _same_json

OBSERVATION_ACCOUNT_CONTRACT = 'earworm/observation-account/v1'
MATTER_CONTEXT_CONTRACT = 'earworm/matter-context/v1'
_MAPPING = 'akouo/masa-observation-report/v0.1'
_NAMESPACE = 'akouo.observation'
_CONTEXT = Draft7Validator(json.loads((_ROOT/'matter-context.schema.json').read_text()))


def _callback_errors(validate, value):
    if not callable(validate):
        raise TypeError('The negotiated mapping validator is required')
    errors = validate(value)
    if not isinstance(errors, list) or any(not isinstance(e, str) for e in errors):
        raise TypeError('Mapping validator must return a list of error strings')
    return errors


def matter_context_errors(value: Any, source: dict, access: dict) -> list[str]:
    if _nonfinite(value):
        return ['Matter context requires finite JSON numbers']
    errors = _errors(_CONTEXT, value)
    if errors:
        return errors
    if not isinstance(source, dict) or not isinstance(source.get('observations'), list) or not isinstance(source.get('sources'), list):
        return ['Matter context requires its retained MASA source']
    errors.extend(listening_access_errors(access))
    if errors:
        return errors
    if source.get('masaVersion') != '0.2.0' or value['source_record_ref'] != source.get('id'):
        errors.append('Matter vocabulary/source identity mismatch')
    for key in ('registers','scales'):
        if not _same_json(value[key], source.get(key)):
            errors.append(f'{key}: source labels must be preserved verbatim')
    selected = [o for o in source['observations'] if isinstance(o, dict) and o.get('id') == value['subject_ref']]
    if len(selected) != 1:
        return errors + ['Matter subject must resolve to one retained Observation']
    observation = selected[0]
    if value['access_declaration_ref'] != access['declaration_id'] or value['subject_ref'] != access['subject_ref']:
        errors.append('Matter context must bind its own access declaration')
    if value['representation']['status'] == 'known' and value['representation']['observation_ref'] != value['subject_ref']:
        errors.append('Structured representation must identify the selected Observation')
    scope = value['temporal_scope']
    if scope['status'] == 'known':
        if scope['window_s']['start'] >= scope['window_s']['end']:
            errors.append('Temporal bounds must increase')
        if scope['resolution_s'] > scope['window_s']['end'] - scope['window_s']['start']:
            errors.append('Resolution exceeds its declared window')
        if scope['domain'] in ('sampled_representation','physical_observation') and scope['sample_rate_hz']['status'] == 'known' and scope['resolution_s'] < 1 / scope['sample_rate_hz']['value']:
            errors.append('Subsample construction does not establish sampled or physical resolution')
        if scope['domain'] == 'sampled_representation':
            sampled = access['sampled_representation']
            if sampled['status'] != 'known' or scope['sample_rate_hz']['status'] != 'known' or sampled['sample_rate_hz'] != scope['sample_rate_hz']['value']:
                errors.append('Sampled scope requires matching declared representation rate')
        if scope['domain'] == 'physical_observation':
            if value['source_modality']['status'] != 'known':
                errors.append('Physical scope requires declared source modality')
            elif value['source_modality']['value'] in ('acoustic','mixed'):
                if access['capture']['status'] != 'known' or access['capture']['apparatus_ref'] not in scope['evidence_refs']:
                    errors.append('Acoustic physical scope requires captured apparatus evidence')
            else:
                apparatus = observation.get('method',{}).get('apparatusRefs',[])
                if not apparatus or not set(apparatus).intersection(scope['evidence_refs']):
                    errors.append('Non-acoustic physical scope requires source-method apparatus evidence')
    return errors


def observation_binding_errors(record: dict) -> list[str]:
    ext = record.get('extensions',{})
    binding, context = ext.get('earworm_observation'), ext.get('earworm_matter_context')
    if not binding:
        if record.get('record_kind') == 'observation_account':
            return ['Observation account requires its binding']
        return ['Matter context currently requires an observation account binding'] if context else []
    errors = []
    if record.get('record_kind') != 'observation_account':
        errors.append('Observation binding requires observation_account record_kind')
    if 'audio' in record:
        errors.append('Structured observation account cannot assert an audio asset')
    if not context:
        return errors + ['Observation account requires matter context']
    wrapped = record.get('listening',{}).get(binding['mapping_namespace'],{})
    mapping = wrapped.get('payload')
    if wrapped.get('contract') != _MAPPING or not isinstance(mapping,dict) or mapping.get('contract') != _MAPPING or not isinstance(mapping.get('report'),dict) or not isinstance(mapping.get('source_snapshot'),dict):
        return errors + ['Unresolved retained observation mapping']
    source, report = mapping['source_snapshot'], mapping['report']
    if not isinstance(source.get('observations'),list) or not isinstance(report.get('features'),list):
        return errors + ['Malformed retained observation/report scope']
    for actual,expected in [(binding['mapping_ref'],mapping.get('mapping_id')),(binding['source_record_ref'],mapping.get('source_record_ref')),(binding['source_record_ref'],source.get('id')),(binding['observation_ref'],mapping.get('source_observation_ref')),(binding['observation_ref'],report.get('subject_ref')),(binding['report_ref'],report.get('report_id')),(context['subject_ref'],binding['observation_ref']),(record.get('subject'),binding['observation_ref'])]:
        if not isinstance(actual,str) or actual != expected:
            errors.append('Observation binding identity mismatch')
    if report.get('contract') != 'akouo/agent-report/v0.1' or mapping.get('attribution') != 'retained_source' or mapping.get('execution') != 'not_requested':
        errors.append('Observation mapping must preserve source attribution and non-execution')
    block = record.get('auditum',{})
    listening = next((item for item in block.get('listenings',[]) if item['listening_id'] == binding['listening_ref']),None)
    if not listening or listening['listener_type'] != 'agent' or listening.get('listener_id') != report.get('listener_id') or listening.get('listening_pass_ref') != report.get('listening_pass_id') or listening.get('report_namespace') != binding['mapping_namespace'] or listening.get('contract') != _MAPPING:
        errors.append('Observation receiving pass is not bound to its mapping')
    decision = next((item for item in block.get('route_decisions',[]) if item['decision_id'] in (listening or {}).get('route_decision_refs',[])),None)
    if not decision or decision['outcome'] != 'proceed' or decision['subject'] != binding['observation_ref'] or decision['authority']['actor'] != report.get('listener_id') or decision.get('listening_id') != binding['listening_ref']:
        errors.append('Observation account requires a bound successful receiving-route decision')
    for feature in report['features']:
        claim = feature.get('claim',{}) if isinstance(feature,dict) else {}
        if not isinstance(feature,dict) or feature.get('category') != 'undetermined' or not isinstance(claim,dict) or claim.get('source') != 'provider' or claim.get('listening_pass_id') != report.get('listening_pass_id'):
            errors.append("Retained observation is not the receiving agent's own measurement")
    access = ext.get('earworm_listening_access')
    if report.get('apparatus_ref') != (access.get('declaration_id') if isinstance(access,dict) else None):
        errors.append('Observation report access mismatch')
    errors.extend(matter_context_errors(context,source,access))
    if not ext.get('earworm_listening_context'):
        errors.append('Observation account requires listening context')
    else:
        context_errors = listening_context_errors(ext['earworm_listening_context'],record)
        errors.extend(context_errors)
        if not context_errors:
            report_context = next((item for item in ext['earworm_listening_context']['contexts'] if item['listening_ref'] == binding['listening_ref']),{})
            if report_context.get('report',{}).get('ref') != report.get('report_id') or not _same_json(report_context.get('recipients'),report.get('recipients')):
                errors.append('Listening context must preserve report identity and recipients')
    try:
        if _instant(record['created_at']) < _instant((listening or {}).get('created_at')) or _instant((listening or {}).get('created_at')) < _instant((decision or {}).get('decided_at')):
            errors.append('Observation listening/route chronology is inconsistent')
        if _instant(record['created_at']) < _instant((decision or {}).get('decided_at')):
            errors.append('Observation account predates its route decision')
    except (ValueError,TypeError):
        errors.append('Observation route chronology is unavailable')
    return errors


def observation_account_errors(record: dict, validate_mapping: Callable) -> list[str]:
    errors = next_record_errors(record)
    if errors:
        return errors
    if record.get('record_kind') != 'observation_account':
        return ['Expected an observation account']
    return _callback_errors(validate_mapping,record['listening'][record['extensions']['earworm_observation']['mapping_namespace']]['payload'])


def create_observation_account(mapping: dict, options: dict, validate_mapping: Callable) -> dict:
    assert_supported_contracts(['earworm/akousma/v1.7','earworm/auditum/v3',OBSERVATION_ACCOUNT_CONTRACT,MATTER_CONTEXT_CONTRACT,_MAPPING,'earworm/listening-access/v1','earworm/listening-context/v1'],options.get('supported_contracts'))
    external = _callback_errors(validate_mapping,mapping)
    if external:
        raise ValueError('; '.join(external))
    for key in ('akousma_id','created_at','originating_app','listening_id','matter_context_id'):
        if not isinstance(options.get(key),str) or not options[key].strip():
            raise ValueError(f'Missing account option: {key}')
    source, report = mapping['source_snapshot'], mapping['report']
    identities = [options['akousma_id'],options['listening_id'],options['matter_context_id']]
    if len(set(identities)) != len(identities) or set(identities).intersection([source['id'],mapping['mapping_id'],report['report_id'],report['listening_pass_id']]):
        raise ValueError('Observation account requires fresh record/context/listening identities')
    decision = deepcopy(options['route_decision'])
    context = dict(contract=MATTER_CONTEXT_CONTRACT,context_id=options['matter_context_id'],vocabulary='masa/0.2.0',source_record_ref=source['id'],subject_ref=report['subject_ref'],registers=deepcopy(source['registers']),scales=deepcopy(source['scales']),source_modality=deepcopy(options['source_modality']),representation=deepcopy(options['representation']),access_declaration_ref=report['apparatus_ref'],temporal_scope=deepcopy(options['temporal_scope']))
    def unknown(reason): return dict(status='unknown',reason=reason)
    result = dict(akousma_id=options['akousma_id'],schema_version='1.7.0',record_kind='observation_account',created_at=options['created_at'],subject=report['subject_ref'],
        provenance=dict(source_type='unknown',origin='unknown',originating_app=options['originating_app'],created_at=options['created_at']),
        lineage=dict(parent_akousma_ids=[]),listening={_NAMESPACE:dict(contract=_MAPPING,payload=deepcopy(mapping))},tags=[],annotations={},
        auditum=dict(contract='earworm/auditum/v3',listenings=[dict(listening_id=options['listening_id'],listener_id=report['listener_id'],listener_type='agent',created_at=options['created_at'],report_namespace=_NAMESPACE,contract=_MAPPING,listening_pass_ref=report['listening_pass_id'],route_decision_refs=[decision['decision_id']])],route_decisions=[decision],actions=[],disagreements=[],honest_absences=[]),
        extensions=dict(earworm_observation=dict(contract=OBSERVATION_ACCOUNT_CONTRACT,mapping_namespace=_NAMESPACE,mapping_ref=mapping['mapping_id'],source_record_ref=source['id'],observation_ref=report['subject_ref'],report_ref=report['report_id'],listening_ref=options['listening_id'],relation='retained_observation_report',execution='not_requested'),earworm_matter_context=context,earworm_listening_access=deepcopy(options['access']),earworm_listening_context=dict(contract='earworm/listening-context/v1',contexts=[dict(listening_ref=options['listening_id'],subject_ref=report['subject_ref'],recipients=deepcopy(report['recipients']),access_declaration_ref=report['apparatus_ref'],report=dict(ref=report['report_id'],contract=_MAPPING,format='structured',readability=dict(status='known',value='machine_readable'),human_rendering=dict(status='none',reason='This binding creates no human rendering.')),renderings=[])],claims=[dict(claim_ref=feature['claim']['claim_id'],listening_ref=options['listening_id'],validity=unknown('No receiving-claim validity policy supplied.'),retention=unknown('No receiving-claim retention policy supplied.')) for feature in report['features']])) )
    errors = next_record_errors(result)
    if errors:
        raise ValueError('; '.join(errors))
    return result
