"""Local sector evidence views and source-preserving scalar descriptor comparisons."""
from __future__ import annotations
import json
import math
from copy import deepcopy
from jsonschema import Draft7Validator
from .listening_contracts import _ROOT, _errors, _nonfinite, assert_supported_contracts
from .listening_context import listening_context_errors
from .record_evolution import next_record_errors, _same_json

MEASUREMENT_SET_CONTRACT='earworm/measurement-set/v1'
AGENT_SECTOR_CONTRACT='earworm/agent-sector/v1'
_SCHEMA=json.loads((_ROOT/'akousma-1.7.schema.json').read_text())
_SET=Draft7Validator(_SCHEMA['$defs']['measurementSet'])
_SECTOR=Draft7Validator(_SCHEMA['$defs']['agentSector'])
_UNITS={'spectral_centroid':{'Hz':'frequency'},'band_energy':{'sample^2':'digital_energy','sample^2*s':'digital_energy'},'level':{'dBFS':'digital_full_scale','LUFS':'perceptual_loudness','dB_SPL':'sound_pressure'},'duration':{'s':'time'}}

def _scalar(v):return isinstance(v,(int,float)) and not isinstance(v,bool) and math.isfinite(v)

def _resolve(value,identity):
    descriptor=next((d for d in value['descriptors'] if d['descriptor_id']==identity),None)
    if descriptor is None:raise ValueError(f'Unresolved measurement descriptor: {identity}')
    source=next((s['record'] for s in value['sources'] if s['record_ref']==descriptor['source_record_ref']),{})
    measurement=next((m for m in source.get('measurements',[]) if m['id']==descriptor['measurement_ref']),None)
    if measurement is None:raise ValueError(f"Unresolved MASA measurement: {descriptor['measurement_ref']}")
    return descriptor,source,measurement


def measurement_set_binding_errors(value):
    if _nonfinite(value):return ['Measurements require finite JSON numbers']
    errors=_errors(_SET,value)
    if errors:return errors
    source_ids,descriptor_ids=set(),set()
    for source in value['sources']:
        if source['record_ref'] in source_ids:errors.append('Duplicate MASA source identity')
        source_ids.add(source['record_ref']);raw=source['record']
        if raw.get('id')!=source['record_ref'] or raw.get('masaVersion')!='0.2.0' or not isinstance(raw.get('measurements'),list) or not isinstance(raw.get('representations'),list):errors.append('Invalid retained MASA source binding')
        elif any(not isinstance(m,dict) or not isinstance(m.get('id'),str) for m in raw['measurements']) or len({m['id'] for m in raw['measurements']})!=len(raw['measurements']):errors.append('Malformed or duplicate MASA measurements')
    if errors:return errors
    for d in value['descriptors']:
        if d['descriptor_id'] in descriptor_ids:errors.append('Duplicate descriptor identity')
        descriptor_ids.add(d['descriptor_id'])
        try:_,source,m=_resolve(value,d['descriptor_id'])
        except ValueError as e:errors.append(str(e));continue
        if m.get('type')!='masa:Measurement' or not isinstance(m.get('metric'),str) or not m['metric'].strip() or not _scalar(m.get('value')) or not isinstance(m.get('unit'),str) or _UNITS[d['feature']].get(m.get('unit'))!=d['reference_basis']:errors.append('Unsupported measurement scalar/unit/reference basis')
        if d['feature']!='level' and (not _scalar(m.get('value')) or m['value']<0):errors.append('Duration, energy and centroid must be nonnegative')
        w=m.get('window')
        if not isinstance(w,dict) or w.get('kind')!='temporal' or w.get('unit')!='s' or not _scalar(w.get('start')) or not _scalar(w.get('end')) or w['start']<0 or w['start']>=w['end']:errors.append('Measurement requires an increasing temporal window in seconds')
        if not any(isinstance(r,dict) and r.get('id')==m.get('about') for r in source['representations']):errors.append('Measurement representation is unresolved')
        method=m.get('method')
        if not isinstance(method,dict) or not isinstance(method.get('name'),str) or not isinstance(method.get('version'),dict) or not isinstance(method.get('parameters'),dict):errors.append('Measurement method must remain attributable')
        band=d['band_hz']
        if band['status']=='known' and band['lower']>=band['upper']:errors.append('Descriptor band must increase')
        if d['feature'] in ('spectral_centroid','band_energy') and band['status']!='known':errors.append('Spectral descriptor requires an explicit band')
        if d['feature']=='spectral_centroid' and band['status']=='known' and _scalar(m.get('value')) and not band['lower']<=m['value']<=band['upper']:errors.append('Centroid falls outside its declared analysis band')
        if d['reference_basis']=='sound_pressure':
            params=method.get('parameters',{}) if isinstance(method,dict) else {}
            if not isinstance(method,dict) or not isinstance(method.get('apparatusRefs'),list) or not method['apparatusRefs'] or not isinstance(params,dict) or not isinstance(params.get('calibration_ref'),str) or not params['calibration_ref'].strip() or not _scalar(params.get('reference_pressure_pa')) or params['reference_pressure_pa']<=0:errors.append('Physical SPL requires declared apparatus, calibration and pressure reference')
    return errors


def measurement_set_errors(value,validate_masa):
    errors=measurement_set_binding_errors(value)
    if errors:return errors
    if not callable(validate_masa):raise TypeError('The negotiated MASA validator is required')
    for source in value['sources']:
        result=validate_masa(source['record'])
        if not isinstance(result,list) or any(not isinstance(e,str) for e in result):raise TypeError('MASA validator must return error strings')
        errors.extend(result)
    return errors


def create_measurement_set(sources,descriptors,validate_masa,supported_contracts):
    assert_supported_contracts([MEASUREMENT_SET_CONTRACT,'masa/0.2.0'],supported_contracts)
    value=dict(contract=MEASUREMENT_SET_CONTRACT,sources=[dict(record_ref=r['id'],record=deepcopy(r)) for r in sources],descriptors=deepcopy(descriptors))
    errors=measurement_set_errors(value,validate_masa)
    if errors:raise ValueError('; '.join(errors))
    return value


def agent_sector_binding_errors(record):
    ext=record.get('extensions',{});measurements=ext.get('earworm_measurements');sector=ext.get('earworm_agent_sector')
    errors=measurement_set_binding_errors(measurements) if 'earworm_measurements' in ext else []
    if sector is None:return errors
    errors.extend(_errors(_SECTOR,sector))
    if errors:return errors
    context=ext.get('earworm_listening_context');errors.extend(listening_context_errors(context,record))
    if errors:return errors
    ids=set();accesses=([ext['earworm_listening_access']] if 'earworm_listening_access' in ext else [])+context.get('access_declarations',[])
    for entry in sector['entries']:
        if entry['sector_id'] in ids:errors.append('Duplicate sector identity')
        ids.add(entry['sector_id'])
        listening=next((l for l in record['auditum']['listenings'] if l['listening_id']==entry['listening_ref']),None)
        ctx=next((c for c in context['contexts'] if c['listening_ref']==entry['listening_ref']),None)
        if ctx is None or listening is None or listening['listener_type'] not in ('agent','sensor','hybrid'):errors.append('Sector requires an attributable agent/sensor/hybrid listening');continue
        access=next((a for a in accesses if a['declaration_id']==entry['access_declaration_ref']),None)
        if access is None or ctx['access_declaration_ref']!=entry['access_declaration_ref'] or ctx['subject_ref']!=entry['subject_ref']:errors.append('Sector subject/access binding mismatch');continue
        claims={c['claim_ref'] for c in context['claims'] if c['listening_ref']==entry['listening_ref']}
        if any(ref not in claims for ref in entry['claim_refs']):errors.append('Sector claim belongs to a missing or different listening')
        allowed_sources={entry['subject_ref'],ctx['report']['ref']}
        if entry['basis']=='retained_measurement' and not entry['measurement_refs']:errors.append('Retained measurement sector requires descriptors')
        if entry['basis']!='retained_measurement' and entry['measurement_refs']:errors.append('Measurement references require retained_measurement basis')
        for ref in entry['measurement_refs']:
            try:d,_,m=_resolve(measurements or {'descriptors':[]},ref)
            except ValueError as e:errors.append(str(e));continue
            allowed_sources.update([m['id'],m['about']])
            if entry['source_kind']!='acoustic_signal':errors.append('Scalar audio descriptors belong to acoustic signal sectors')
            model=access['model_input']
            if model['status']!='known' or model['representation_ref']!=m['about']:errors.append('Acoustic sector measurement must resolve to the effective input')
            else:
                if m['window']['start']<model['window_s']['start'] or m['window']['end']>model['window_s']['end']:errors.append('Measurement window exceeds the effective input')
                if d['band_hz']['status']=='known' and (d['band_hz']['lower']<model['effective_band_hz']['lower'] or d['band_hz']['upper']>model['effective_band_hz']['upper']):errors.append('Descriptor band exceeds the effective input')
        if entry['source_kind']=='non_acoustic_observation' or entry['basis']=='retained_observation':
            binding=ext.get('earworm_observation',{});modality=ext.get('earworm_matter_context',{}).get('source_modality',{})
            if entry['source_kind']!='non_acoustic_observation' or entry['basis']!='retained_observation' or binding.get('listening_ref')!=entry['listening_ref'] or binding.get('observation_ref')!=entry['subject_ref'] or modality.get('status')!='known' or modality.get('value')!='non_acoustic':errors.append('Non-acoustic sector requires its explicit observation binding')
        if ext.get('earworm_observation',{}).get('listening_ref')==entry['listening_ref'] and entry['source_kind']=='acoustic_signal':errors.append('Structured observation cannot become an acoustic signal sector')
        for ref in entry['renderings']:
            rendering=next((r for r in ctx['renderings'] if r['rendering_id']==ref),None)
            if rendering is None:errors.append('Sector rendering must resolve within its own listening')
            elif rendering['source_ref'] not in allowed_sources:errors.append('Sector rendering source is unrelated to its evidence')
    return errors


def agent_sector_view(record,sector_id):
    errors=next_record_errors(record)
    if errors:raise ValueError('; '.join(errors))
    entry=next((e for e in record.get('extensions',{}).get('earworm_agent_sector',{}).get('entries',[]) if e['sector_id']==sector_id),None)
    if entry is None:raise ValueError('Unknown sector')
    ext=record['extensions'];context=ext['earworm_listening_context'];ctx=next(c for c in context['contexts'] if c['listening_ref']==entry['listening_ref'])
    access=next(a for a in ([ext['earworm_listening_access']] if 'earworm_listening_access' in ext else [])+context.get('access_declarations',[]) if a['declaration_id']==entry['access_declaration_ref'])
    measurements=[]
    for ref in entry['measurement_refs']:
        descriptor,_,measurement=_resolve(ext['earworm_measurements'],ref);measurements.append(dict(descriptor=descriptor,measurement=measurement))
    return deepcopy(dict(entry=entry,access=access,renderings=[r for r in ctx['renderings'] if r['rendering_id'] in entry['renderings']],measurements=measurements))


def _comparison(source,target,options):
    if source['akousma_id']==target['akousma_id']:raise ValueError('Similarity requires two distinct records')
    ld,ls,l=_resolve(source.get('extensions',{}).get('earworm_measurements',{'descriptors':[]}),options['source_descriptor_ref'])
    rd,rs,r=_resolve(target.get('extensions',{}).get('earworm_measurements',{'descriptors':[]}),options['target_descriptor_ref'])
    for key in ('feature','reference_basis','band_hz'):
        if not _same_json(ld[key],rd[key]):raise ValueError(f'Incompatible descriptor {key}')
    if l['unit']!=r['unit'] or l['metric']!=r['metric'] or not _same_json(l['window'],r['window']) or l['method']['name']!=r['method']['name'] or l['method']['version'].get('state')!='known' or not isinstance(l['method']['version'].get('value'),str) or not l['method']['version']['value'].strip() or not _same_json(l['method']['version'],r['method']['version']) or not _same_json(l['method']['parameters'],r['method']['parameters']):raise ValueError('Comparison requires matching metrics, units, windows and versioned methods')
    if ls['id']==rs['id'] and not _same_json(ls,rs) or l['id']==r['id'] and not _same_json(l,r):raise ValueError('Conflicting retained source or measurement identity')
    distance=abs(l['value']-r['value'])
    if not math.isfinite(distance):raise ValueError('Scalar difference is not finite')
    return dict(contract='earworm/relations/v1',relation_id=options['relation_id'],type='similar_by',target_akousma_id=target['akousma_id'],declared_by=options['declared_by'],evidence_refs=list(dict.fromkeys([l['id'],r['id']])),epistemic_status='inferred',review=dict(status='unreviewed'),criterion=dict(criterion_id=options['criterion_id'],feature=ld['feature'],unit=l['unit'],method_ref='earworm:absolute-difference',method_revision='1',input_refs=[source['akousma_id'],target['akousma_id']],normalization='none',score=dict(status='known',value=distance,policy='absolute_difference; lower is closer under this descriptor only'),descriptor_refs=[dict(record_ref=source['akousma_id'],descriptor_ref=options['source_descriptor_ref']),dict(record_ref=target['akousma_id'],descriptor_ref=options['target_descriptor_ref'])]))


def compare_measurement_descriptors(source,target,options):
    assert_supported_contracts(['earworm/akousma/v1.7',MEASUREMENT_SET_CONTRACT,'earworm/relations/v1'],options.get('supported_contracts'))
    for key in ('relation_id','criterion_id','declared_by'):
        if not isinstance(options.get(key),str) or not options[key].strip():raise ValueError(f'Missing comparison option: {key}')
    errors=next_record_errors(source)+next_record_errors(target)
    if errors:raise ValueError('; '.join(errors))
    return _comparison(source,target,options)


def descriptor_relation_errors(record,scope):
    errors=[]
    for relation in record['lineage'].get('relations',[]):
        refs=relation.get('criterion',{}).get('descriptor_refs')
        if refs is None:continue
        if relation['type']!='similar_by' or len(refs)!=2 or refs[0]['record_ref']!=record['akousma_id'] or refs[1]['record_ref']!=relation['target_akousma_id']:errors.append('Descriptor comparison requires ordered source/target record references');continue
        target=scope.get(refs[1]['record_ref'])
        if target is None:errors.append('Unresolved descriptor comparison target');continue
        try:
            expected=_comparison(record,target,dict(relation_id=relation['relation_id'],criterion_id=relation['criterion']['criterion_id'],declared_by=relation['declared_by'],source_descriptor_ref=refs[0]['descriptor_ref'],target_descriptor_ref=refs[1]['descriptor_ref']))
            if not _same_json(expected['criterion'],relation['criterion']) or not _same_json(expected['evidence_refs'],relation['evidence_refs']) or relation['epistemic_status']!='inferred':errors.append('Descriptor comparison differs from its retained inputs')
        except (ValueError,KeyError,TypeError) as e:errors.append(str(e))
    return errors
