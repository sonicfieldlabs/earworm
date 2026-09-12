"""Spec 1.8 admission; no dependency on AKOÚŌ and no implicit object downloads."""
from copy import deepcopy
import json
import math
from pathlib import Path
from jsonschema import Draft7Validator
from .listening_contracts import _nonfinite

ROOT = Path(__file__).parent


def spectral_bundle_errors(bundle, *, resolve_object=None):
    if _nonfinite(bundle): return ['Nonfinite spectral value']
    errors = [e.message for e in Draft7Validator(json.loads((ROOT/'spectral-bundle.schema.json').read_text())).iter_errors(bundle)]
    if errors: return errors
    if bundle['source_interval_samples'][0] >= bundle['source_interval_samples'][1]: errors.append('Invalid source interval')
    ids = [v['view_id'] for v in bundle['views']]
    if len(set(ids)) != len(ids): errors.append('Duplicate view identity')
    for v in bundle['views']:
        s = v['settings']
        if not 0 <= s['f_min'] < s['f_max'] <= bundle['effective_rate_hz']/2: errors.append('Invalid frequency bounds')
        if v['kind'].startswith('projection_') and (v['for'] != 'human' or not v['losses']): errors.append('Projection must declare human target and losses')
        if v['state'] != 'retained': continue
        if v['sha256'] != v['object_ref'].split('/')[-1].split('.')[0]: errors.append('Object hash mismatch')
        width = dict(float32=4,float64=8,complex64=8,complex128=16,uint8=1)[v['dtype']]
        if math.prod(v['shape'])*width != v['expanded_bytes']: errors.append('Shape/dtype/expanded-byte mismatch')
        if len(v['shape']) != len(v['axis_order']) or len(v['shape']) != len(v['axis_units']): errors.append('Axis dimensions mismatch')
        if resolve_object is not None:
            actual = resolve_object(v['object_ref'])
            if not isinstance(actual,dict) or any(actual.get(k)!=v[k] for k in ('sha256','dtype','shape','byte_count','expanded_bytes')): errors.append('Object metadata unavailable or mismatched')
    return errors


def record_18_errors(record, *, validate_native=None, resolve_object=None):
    if _nonfinite(record): return ['Nonfinite record value']
    errors = [e.message for e in Draft7Validator(json.loads((ROOT/'akousma-1.8.schema.json').read_text())).iter_errors(record)]
    if errors: return errors
    # Reuse 1.7 semantic checks without altering the frozen schema or caller record.
    from .record_evolution import next_record_errors
    base = deepcopy(record); base['schema_version']='1.7.0'
    errors.extend(next_record_errors(base))
    ext = record.get('extensions',{})
    if 'oida.spectral' in ext: errors.extend(spectral_bundle_errors(ext['oida.spectral'],resolve_object=resolve_object))
    if 'akouo.agent-native' in ext:
        if not callable(validate_native): errors.append('Native evidence unvalidated: host validator unavailable')
        else:
            result=validate_native(ext['akouo.agent-native'])
            if not isinstance(result,list) or any(not isinstance(e,str) for e in result): raise TypeError('Host validator must return error strings')
            errors.extend(result)
    return errors


def admit_record(record, *, supported_versions, validate_native=None, resolve_object=None, resolve_representation=None):
    if record.get('schema_version') not in supported_versions: raise ValueError('Consumer has not admitted this record version; no downgrade')
    if record.get('schema_version')=='1.8.0':
        errors=record_18_errors(record,validate_native=validate_native,resolve_object=resolve_object)
        if 'oida.spectral' in record.get('extensions',{}) and resolve_object is None: errors.append('Retained object host validation unavailable')
        bundle=record.get('extensions',{}).get('oida.spectral')
        if bundle:
            actual=resolve_representation(bundle['sampled_representation']) if callable(resolve_representation) else None
            keys=('subject_ref','excerpt_sha256','record_ref','source_interval_samples','effective_rate_hz','channel_layout')
            if not isinstance(actual,dict) or any(actual.get(k)!=bundle[k] for k in keys): errors.append('Sampled representation identity/scope unvalidated')
            if bundle['record_ref'] != record['akousma_id']: errors.append('Bundle belongs to another record')
    else:
        from . import validation_errors
        errors=validation_errors(record)
    if errors: raise ValueError('; '.join(errors))
    return deepcopy(record)
