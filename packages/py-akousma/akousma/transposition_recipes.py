"""Typed application checks on completed transposition receipts; no DSP."""
import json
import math
import re
from jsonschema import Draft7Validator
from .listening_contracts import _ROOT, _errors, _nonfinite

TRANSPOSITION_RECIPE_CONTRACT = 'earworm/transposition-recipe/v1'
_DEFINITION = json.loads((_ROOT / 'transposition-recipe.schema.json').read_text())
_SCHEMA = Draft7Validator(_DEFINITION)
_PARAMETERS = {kind: Draft7Validator(definition) for kind, definition in _DEFINITION['$defs'].items()}
_OPERATIONS = dict(filtered_resample='earworm:resample', playback_rate='earworm:playback_rate', frequency_translation='earworm:frequency_translate', pitch_shift='matter.pitchshift')

def _number(v):
    try:
        return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
    except OverflowError:
        return False

def _close(a, b):
    return _number(a) and _number(b) and abs(a - b) <= 1e-9 * max(1, abs(a), abs(b))

def _text(v):
    return isinstance(v, str) and bool(v.strip())

def transposition_recipe_errors(source):
    """Additional application checks; the host must separately validate full MASA."""
    if not isinstance(source, dict) or not isinstance(source.get('history'), dict) or source['history'].get('mode') != 'embedded' or not isinstance(source['history'].get('events'), list) or not isinstance(source.get('representations'), list):
        return ['Recipe source requires embedded events and representations']
    if _nonfinite(source):
        return ['Recipe source requires finite JSON numbers']
    errors = []
    for event in source['history']['events']:
        if not isinstance(event, dict):
            errors.append('Malformed operation receipt'); continue
        ext = event.get('extensions', {})
        recipe = ext.get('earworm:transposition') if isinstance(ext, dict) else None
        if not isinstance(ext, dict) or 'earworm:transposition' not in ext:
            if event.get('operationType') in [v for v in _OPERATIONS.values() if v.startswith('earworm:')]:
                errors.append('Application transposition operation requires its typed recipe')
            continue
        shape = _errors(_SCHEMA, recipe)
        if shape:
            errors.extend(shape); continue
        if (event.get('operationType') != _OPERATIONS[recipe['kind']] or event.get('finalStatus') != 'completed' or event.get('effectClass') not in ('derive', 'transform')
                or not isinstance(event.get('policyEvaluation'), dict) or event['policyEvaluation'].get('result') != 'permitted'
                or not isinstance(event.get('inputs'), list) or not isinstance(event.get('outputs'), list)
                or len(event['inputs']) != 1 or len(event['outputs']) != 1 or event['inputs'][0] == event['outputs'][0]):
            errors.append('Recipe requires the matching permitted completed unary transformation'); continue
        if not isinstance(event.get('parameters'), dict):
            errors.append('Recipe parameters must be an object'); continue
        parameter_errors = _errors(_PARAMETERS[recipe['kind']], event['parameters'])
        if parameter_errors:
            errors.extend(parameter_errors); continue
        reps = [next((r for r in source['representations'] if isinstance(r, dict) and r.get('id') == ref), {}) for ref in [event['inputs'][0], event['outputs'][0]]]
        values = []
        for rep in reps:
            technical = [(rep.get('audio') if isinstance(rep.get('audio'), dict) else {}).get(k) for k in ['sampleRateHz', 'durationSeconds', 'channels']]
            if any(not isinstance(v, dict) or v.get('state') != 'known' or not _number(v.get('value')) or v['value'] <= 0 for v in technical) or not float(technical[2]['value']).is_integer():
                errors.append('Recipe requires known positive rates/durations and integer channels'); break
            values.append([v['value'] for v in technical])
            integrity = rep.get('integrity', {})
            if (not isinstance(integrity, dict) or integrity.get('state') not in ('known', 'unknown', 'unavailable', 'withheld', 'deleted')
                    or integrity.get('state') == 'known' and (not isinstance(integrity.get('value'), dict) or not isinstance(integrity['value'].get('sha256'), str) or not re.fullmatch(r'[a-fA-F0-9]{64}', integrity['value']['sha256']))):
                errors.append('Recipe integrity must retain qualified absence or a declared SHA-256')
        if len(values) != 2:
            continue
        (in_rate, in_duration, in_channels), (out_rate, out_duration, out_channels) = values
        if in_channels != out_channels:
            errors.append('Transposition recipe cannot silently mix channels')
        tool = event.get('tool', {}); engine = tool.get('value', {}) if isinstance(tool, dict) else {}
        if not isinstance(tool, dict) or tool.get('state') != 'known' or not isinstance(engine, dict) or not _text(engine.get('name')) or not isinstance(engine.get('version'), dict) or engine['version'].get('state') != 'known' or not _text(engine['version'].get('value')):
            errors.append('Recipe requires a named versioned engine')
        window = recipe['input_window_s']; duration = window['end'] - window['start']
        if duration <= 0 or window['end'] > in_duration:
            errors.append('Recipe window must lie within the source duration')
        a, b = recipe['input_band_hz'], recipe['output_band_hz']
        for band, rate in [(a, in_rate), (b, out_rate)]:
            if band['lower'] >= band['upper'] or band['upper'] > rate / 2:
                errors.append('Recipe band must increase within its representation Nyquist limit')
        if (recipe['duration_behavior'] == 'preserved') != _close(duration, out_duration):
            errors.append('Declared duration behavior disagrees with representation duration')
        p = event.get('parameters', {})
        if recipe['kind'] == 'filtered_resample':
            if recipe['duration_behavior'] != 'preserved' or _close(in_rate, out_rate) or b['lower'] < a['lower'] or b['upper'] > a['upper']:
                errors.append('Filtered resampling needs a new rate, preserved duration and retained sub-band')
        elif recipe['kind'] == 'playback_rate':
            ratio = p.get('rate_ratio')
            if not _number(ratio) or ratio <= 0 or not _close(out_rate, in_rate * ratio) or not _close(out_duration, duration / ratio) or not _close(b['lower'], a['lower'] * ratio) or not _close(b['upper'], a['upper'] * ratio):
                errors.append('Playback-rate ratio must bind rate, duration and band scaling')
        elif recipe['kind'] == 'frequency_translation':
            offset = p.get('offset_hz')
            if not _number(offset) or recipe['duration_behavior'] != 'preserved' or not _close(b['lower'], a['lower'] + offset) or not _close(b['upper'], a['upper'] + offset):
                errors.append('Frequency translation requires an additive Hz mapping and preserved duration')
        else:
            cents = p.get('cents')
            if not _number(cents) or not -14400 <= cents <= 14400 or not _close(b['lower'], a['lower'] * 2 ** (cents / 1200)) or not _close(b['upper'], a['upper'] * 2 ** (cents / 1200)):
                errors.append('Pitch shifting requires the declared cents-based frequency ratio')
    return errors
