/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */
import schema from '@earworm/core/schemas/transposition-recipe.schema.json' with { type: 'json' };
import { compileContractSchema, schemaErrors } from './listening-contracts.js';
export const TRANSPOSITION_RECIPE_CONTRACT = 'earworm/transposition-recipe/v1';
const validate = compileContractSchema(schema);
const parameters = Object.fromEntries(Object.entries(schema.$defs).map(([kind, definition]) => [kind, compileContractSchema(definition)]));
const finite = v => typeof v === 'number' ? Number.isFinite(v) : v && typeof v === 'object' ? Object.values(v).every(finite) : true;
const operations = { filtered_resample: 'earworm:resample', playback_rate: 'earworm:playback_rate', frequency_translation: 'earworm:frequency_translate', pitch_shift: 'matter.pitchshift' };
const number = v => typeof v === 'number' && Number.isFinite(v);
const close = (a, b) => number(a) && number(b) && Math.abs(a - b) <= 1e-9 * Math.max(1, Math.abs(a), Math.abs(b));
const text = v => typeof v === 'string' && v.trim().length > 0;

/** Additional application checks only; full MASA validation is required at ingress. */
export function transpositionRecipeErrors(source) {
  if (!finite(source)) return ['Recipe source requires finite JSON numbers'];
  if (source?.history?.mode !== 'embedded' || !Array.isArray(source?.history?.events) || !Array.isArray(source?.representations)) return ['Recipe source requires embedded events and representations'];
  const errors = [];
  for (const event of source.history.events) {
    if (!event || typeof event !== 'object') { errors.push('Malformed operation receipt'); continue; }
    const recipe = event?.extensions?.['earworm:transposition'];
    if (recipe === undefined) {
      if (Object.values(operations).filter(v => v.startsWith('earworm:')).includes(event?.operationType)) errors.push('Application transposition operation requires its typed recipe');
      continue;
    }
    const shape = schemaErrors(validate, recipe);
    if (shape.length) { errors.push(...shape); continue; }
    if (event.operationType !== operations[recipe.kind] || event.finalStatus !== 'completed' || !['derive', 'transform'].includes(event.effectClass) || event.policyEvaluation?.result !== 'permitted' ||
        !Array.isArray(event.inputs) || !Array.isArray(event.outputs) || event.inputs.length !== 1 || event.outputs.length !== 1 || event.inputs[0] === event.outputs[0]) {
      errors.push('Recipe requires the matching permitted completed unary transformation'); continue;
    }
    if (!event.parameters || typeof event.parameters !== 'object' || Array.isArray(event.parameters)) { errors.push('Recipe parameters must be an object'); continue; }
    const parameterErrors = schemaErrors(parameters[recipe.kind], event.parameters);
    if (parameterErrors.length) { errors.push(...parameterErrors); continue; }
    const input = source.representations.find(r => r?.id === event.inputs[0]);
    const output = source.representations.find(r => r?.id === event.outputs[0]);
    const values = [];
    for (const rep of [input, output]) {
      const technical = ['sampleRateHz', 'durationSeconds', 'channels'].map(k => rep?.audio?.[k]);
      if (technical.some(v => v?.state !== 'known' || !number(v.value) || v.value <= 0) || !Number.isInteger(technical[2]?.value)) {
        errors.push('Recipe requires known positive rates/durations and integer channels'); break;
      }
      values.push(technical.map(v => v.value));
      const integrity = rep.integrity;
      if (!integrity || !['known', 'unknown', 'unavailable', 'withheld', 'deleted'].includes(integrity.state) ||
          integrity.state === 'known' && !/^[a-fA-F0-9]{64}$/.test(integrity.value?.sha256 ?? '')) errors.push('Recipe integrity must retain qualified absence or a declared SHA-256');
    }
    if (values.length !== 2) continue;
    const [[inRate, inDuration, inChannels], [outRate, outDuration, outChannels]] = values;
    if (inChannels !== outChannels) errors.push('Transposition recipe cannot silently mix channels');
    const tool = event.tool;
    if (tool?.state !== 'known' || !text(tool.value?.name) || tool.value?.version?.state !== 'known' || !text(tool.value.version.value)) errors.push('Recipe requires a named versioned engine');
    const window = recipe.input_window_s, duration = window.end - window.start;
    if (duration <= 0 || window.end > inDuration) errors.push('Recipe window must lie within the source duration');
    const a = recipe.input_band_hz, b = recipe.output_band_hz;
    for (const [band, rate] of [[a, inRate], [b, outRate]]) if (band.lower >= band.upper || band.upper > rate / 2) errors.push('Recipe band must increase within its representation Nyquist limit');
    if ((recipe.duration_behavior === 'preserved') !== close(duration, outDuration)) errors.push('Declared duration behavior disagrees with representation duration');
    const p = event.parameters ?? {};
    if (recipe.kind === 'filtered_resample') {
      if (recipe.duration_behavior !== 'preserved' || close(inRate, outRate) || b.lower < a.lower || b.upper > a.upper) errors.push('Filtered resampling needs a new rate, preserved duration and retained sub-band');
    } else if (recipe.kind === 'playback_rate') {
      const ratio = p.rate_ratio;
      if (!number(ratio) || ratio <= 0 || !close(outRate, inRate * ratio) || !close(outDuration, duration / ratio) || !close(b.lower, a.lower * ratio) || !close(b.upper, a.upper * ratio)) errors.push('Playback-rate ratio must bind rate, duration and band scaling');
    } else if (recipe.kind === 'frequency_translation') {
      if (!number(p.offset_hz) || recipe.duration_behavior !== 'preserved' || !close(b.lower, a.lower + p.offset_hz) || !close(b.upper, a.upper + p.offset_hz)) errors.push('Frequency translation requires an additive Hz mapping and preserved duration');
    } else {
      if (!number(p.cents) || p.cents < -14400 || p.cents > 14400 || !close(b.lower, a.lower * 2 ** (p.cents / 1200)) || !close(b.upper, a.upper * 2 ** (p.cents / 1200))) errors.push('Pitch shifting requires the declared cents-based frequency ratio');
    }
  }
  return errors;
}
