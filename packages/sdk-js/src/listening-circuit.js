/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */
// Listening circuits (the moves a listening loop made) and run memory (what a run remembers).
// Parity with py-akousma's akousma.listening_circuit on tests/contracts/circuit.
import circuitSchema from '@earworm/core/schemas/listening-circuit.schema.json' with { type: 'json' };
import memorySchema from '@earworm/core/schemas/run-memory.schema.json' with { type: 'json' };
import { compileContractSchema, schemaErrors } from './listening-contracts.js';

export const LISTENING_CIRCUIT_CONTRACT = 'earworm/listening-circuit/v1';
export const RUN_MEMORY_CONTRACT = 'earworm/run-memory/v1';
export const CIRCUIT_EXTENSION = 'earworm_listening_circuit';
export const RECENT_LIMIT = 64;
export const SOURCE_LIMIT = 256;

const validateCircuit = compileContractSchema(circuitSchema);
const validateMemory = compileContractSchema(memorySchema);
const LISTENING_MOVES = new Set(['relisten_same', 'new_fragment', 'switch_source']);
const finite = v => typeof v === 'number' ? Number.isFinite(v) : v && typeof v === 'object' ? Object.values(v).every(finite) : true;
const instant = v => Date.parse(v);

function listeningIds(record) {
  const listenings = record?.auditum?.listenings;
  if (!Array.isArray(listenings)) return null;
  return new Set(listenings.filter(l => l && typeof l === 'object' && l.listening_id).map(l => String(l.listening_id)));
}

/** Shape and coherence errors for one circuit; with a record, listening references must resolve. */
export function listeningCircuitErrors(value, record) {
  if (!finite(value)) return ['Listening circuit requires finite JSON numbers'];
  const errors = schemaErrors(validateCircuit, value);
  if (errors.length) return errors;
  const known = record === undefined || record === null ? null : listeningIds(record);
  if (record !== undefined && record !== null && known === null) errors.push("A circuit's record must carry an auditum with listenings");
  const seen = new Set();
  for (const step of value.steps) {
    const where = `steps[${step.step_id}]`;
    if (seen.has(step.step_id)) errors.push(`${where}: duplicate step id`);
    seen.add(step.step_id);
    const offered = new Map();
    for (const candidate of step.offered) {
      if (offered.has(candidate.id)) errors.push(`${where}: duplicate offered candidate ${candidate.id}`);
      offered.set(candidate.id, candidate);
    }
    const { move, chosen } = step;
    const status = step.outcome.status;
    if (chosen === null) {
      if (move !== 'stop' && !['refused', 'blocked', 'failed'].includes(status)) errors.push(`${where}: only a stop or an unexecuted step may choose nothing`);
    } else if (!offered.has(chosen)) errors.push(`${where}: the chosen candidate was not offered`);
    else if (offered.get(chosen).move !== move) errors.push(`${where}: the chosen candidate's move differs from the step's move`);
    if ((move === 'sound') !== (step.layer === 'sounding')) errors.push(`${where}: a sounding layer belongs to a sound move, and only to one`);
    if (move === 'stop' && step.layer !== 'closing') errors.push(`${where}: a stop closes the circuit`);
    const maxDepth = step.bounds?.max_depth;
    if (maxDepth !== undefined && maxDepth !== null && step.depth > maxDepth) errors.push(`${where}: depth exceeds the declared maximum`);
    if (status === 'executed') {
      if (move === 'sound' && !step.to_akousma_id) errors.push(`${where}: an executed sound names the record of what was sounded`);
      if (LISTENING_MOVES.has(move) && !(step.to_listening_id || step.to_akousma_id)) errors.push(`${where}: an executed ${move} names the listening or record it produced`);
    }
    if (known) {
      const keys = step.from_akousma_id ? ['to_listening_id'] : ['to_listening_id', 'from_listening_id'];
      for (const key of keys) {
        const ref = step[key];
        if (ref !== undefined && ref !== null && !known.has(ref)) errors.push(`${where}: ${key} does not resolve to this record's listenings`);
      }
    }
  }
  return errors;
}

/** Errors in a record's circuit extension; [] when it carries none. */
export function circuitRecordErrors(record) {
  const extensions = record?.extensions;
  if (!extensions || typeof extensions !== 'object' || !(CIRCUIT_EXTENSION in extensions)) return [];
  return listeningCircuitErrors(extensions[CIRCUIT_EXTENSION], record);
}

export function runMemoryErrors(value) {
  if (!finite(value)) return ['Run memory requires finite JSON numbers'];
  const errors = schemaErrors(validateMemory, value);
  if (errors.length) return errors;
  if (instant(value.updated_at) < instant(value.started_at)) errors.push('Run memory cannot be updated before it started');
  if (Object.keys(value.sources).length > SOURCE_LIMIT) errors.push(`A run memory keeps at most ${SOURCE_LIMIT} sources`);
  const windows = value.totals.windows;
  for (const [key, source] of Object.entries(value.sources)) {
    if (source.last_window > windows) errors.push(`sources[${key}]: last window is beyond the run's windows`);
    if (source.dwell > source.windows || source.visits > source.windows) errors.push(`sources[${key}]: dwell and visits cannot exceed windows heard`);
  }
  if (value.current_source !== undefined && value.current_source !== null && !(value.current_source in value.sources)) errors.push('The current source must be one the run has heard');
  return errors;
}

export function emptyRunMemory(sessionId, startedAt) {
  const memory = {
    contract: RUN_MEMORY_CONTRACT, session_id: sessionId, started_at: startedAt, updated_at: startedAt, revision: 0,
    current_source: null, sources: {}, totals: { windows: 0, steps: 0, moves: {}, layers: {} }, recent: []
  };
  const errors = runMemoryErrors(memory);
  if (errors.length) throw new Error(errors.join('; '));
  return memory;
}

const count = (table, key, by = 1) => { table[key] = (table[key] ?? 0) + by; };

/** A new run memory with one more window heard from sourceKey; the inputs are not changed. */
export function foldRunMemory(memory, { at, source_key: sourceKey, akousma_id: akousmaId = null, circuit = null, heard_as: heardAs = [], modes = [], declined = false, repeated = false }) {
  let errors = runMemoryErrors(memory);
  if (errors.length) throw new Error('Invalid run memory: ' + errors.join('; '));
  if (circuit !== null) {
    errors = listeningCircuitErrors(circuit);
    if (errors.length) throw new Error('Invalid listening circuit: ' + errors.join('; '));
    if (circuit.run.session_id !== memory.session_id) throw new Error('The circuit belongs to another run');
    if (circuit.run.source_key !== sourceKey) throw new Error('The circuit belongs to another source');
  }
  if (instant(at) < instant(memory.updated_at)) throw new Error('A run memory folds windows in time order');
  const out = structuredClone(memory);
  out.totals.windows += 1;
  const window = out.totals.windows;
  let source = out.sources[sourceKey];
  if (!source) source = out.sources[sourceKey] = {
    first_heard_at: at, last_heard_at: at, windows: 0, visits: 0, dwell: 0, last_window: 0,
    heard_as: {}, modes: {}, declined: 0, repeated: 0, soundings: 0, last_route: null
  };
  if (out.current_source !== sourceKey) { source.visits += 1; source.dwell = 0; }
  source.dwell += 1;
  source.windows += 1;
  source.last_heard_at = at;
  source.last_window = window;
  for (const kind of new Set(heardAs)) count(source.heard_as, String(kind));
  for (const mode of new Set(modes)) count(source.modes, String(mode));
  source.declined += declined ? 1 : 0;
  source.repeated += repeated ? 1 : 0;
  const steps = circuit?.steps ?? [];
  for (const step of steps) {
    out.totals.steps += 1;
    count(out.totals.moves, step.move);
    count(out.totals.layers, step.layer);
    if (step.move === 'sound' && step.outcome.status === 'executed') source.soundings += 1;
    const route = step.route;
    if (route) source.last_route = { primary: route.primary, secondary: route.secondary ?? null, corrective: route.corrective ?? null, confidence: route.confidence };
    out.recent.push({ at: step.at, source_key: sourceKey, move: step.move, layer: step.layer, akousma_id: step.to_akousma_id || akousmaId, primary: route ? route.primary : null });
  }
  if (!steps.length) out.recent.push({ at, source_key: sourceKey, move: 'listen', layer: 'general', akousma_id: akousmaId, primary: null });
  out.recent.splice(0, Math.max(0, out.recent.length - RECENT_LIMIT));
  out.current_source = sourceKey;
  out.updated_at = at;
  out.revision += 1;
  errors = runMemoryErrors(out);
  if (errors.length) throw new Error('Folding produced an invalid run memory: ' + errors.join('; '));
  return out;
}

/** Windows heard since this source was last heard, or null if the run never heard it. */
export function windowsSince(memory, sourceKey) {
  const source = memory?.sources?.[sourceKey];
  return source ? memory.totals.windows - source.last_window : null;
}
