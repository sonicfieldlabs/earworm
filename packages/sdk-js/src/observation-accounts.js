/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */
import contextSchema from '@earworm/core/schemas/matter-context.schema.json' with { type: 'json' };
import { compileContractSchema, schemaErrors, listeningAccessErrors, assertSupportedContracts } from './listening-contracts.js';
import { listeningContextErrors, parseContractInstant } from './listening-context.js';
import { nextRecordErrors } from './record-evolution.js';

export const OBSERVATION_ACCOUNT_CONTRACT = 'earworm/observation-account/v1';
export const MATTER_CONTEXT_CONTRACT = 'earworm/matter-context/v1';
const MAPPING = 'akouo/masa-observation-report/v0.1';
const NAMESPACE = 'akouo.observation';
const validateContext = compileContractSchema(contextSchema);
const object = v => v !== null && typeof v === 'object' && !Array.isArray(v);
const same = (a,b) => stable(a) === stable(b);
function stable(value) {
  if (Array.isArray(value)) return `[${value.map(stable).join(',')}]`;
  if (object(value)) return `{${Object.keys(value).sort().map(k=>`${JSON.stringify(k)}:${stable(value[k])}`).join(',')}}`;
  return JSON.stringify(value);
}
function callbackErrors(validate, value) {
  if (typeof validate !== 'function') throw new TypeError('The negotiated mapping validator is required');
  const errors = validate(value);
  if (!Array.isArray(errors) || errors.some(e=>typeof e !== 'string')) throw new TypeError('Mapping validator must return an array of error strings');
  return errors;
}

/** Validate separate source labels and evidence domains; never infer audibility. */
export function matterContextErrors(value, source, access) {
  const errors = schemaErrors(validateContext, value);
  if (errors.length) return errors;
  if (!object(source) || !Array.isArray(source.observations) || !Array.isArray(source.sources)) return ['Matter context requires its retained MASA source'];
  errors.push(...listeningAccessErrors(access));
  if (errors.length) return errors;
  if (source.masaVersion !== '0.2.0' || value.source_record_ref !== source.id) errors.push('Matter vocabulary/source identity mismatch');
  for (const key of ['registers','scales']) if (!same(value[key],source[key])) errors.push(`${key}: source labels must be preserved verbatim`);
  const selected = source.observations.filter(o=>object(o) && o.id === value.subject_ref);
  if (selected.length !== 1) return [...errors,'Matter subject must resolve to one retained Observation'];
  const observation = selected[0];
  if (value.access_declaration_ref !== access.declaration_id || value.subject_ref !== access.subject_ref) errors.push('Matter context must bind its own access declaration');
  if (value.representation.status === 'known' && value.representation.observation_ref !== value.subject_ref) errors.push('Structured representation must identify the selected Observation');
  const scope = value.temporal_scope;
  if (scope.status === 'known') {
    if (scope.window_s.start >= scope.window_s.end) errors.push('Temporal bounds must increase');
    if (scope.resolution_s > scope.window_s.end - scope.window_s.start) errors.push('Resolution exceeds its declared window');
    if (['sampled_representation','physical_observation'].includes(scope.domain) && scope.sample_rate_hz.status === 'known' && scope.resolution_s < 1 / scope.sample_rate_hz.value) errors.push('Subsample construction does not establish sampled or physical resolution');
    if (scope.domain === 'sampled_representation') {
      const sampled = access.sampled_representation;
      if (sampled.status !== 'known' || scope.sample_rate_hz.status !== 'known' || sampled.sample_rate_hz !== scope.sample_rate_hz.value) errors.push('Sampled scope requires matching declared representation rate');
    }
    if (scope.domain === 'physical_observation') {
      if (value.source_modality.status !== 'known') errors.push('Physical scope requires declared source modality');
      else if (['acoustic','mixed'].includes(value.source_modality.value)) {
        if (access.capture.status !== 'known' || !scope.evidence_refs.includes(access.capture.apparatus_ref)) errors.push('Acoustic physical scope requires captured apparatus evidence');
      } else {
        const apparatus = observation.method?.apparatusRefs ?? [];
        if (!apparatus.length || !apparatus.some(ref=>scope.evidence_refs.includes(ref))) errors.push('Non-acoustic physical scope requires source-method apparatus evidence');
      }
    }
  }
  return errors;
}

/** Record-local binding only; use observationAccountErrors for foreign conformance. */
export function observationBindingErrors(record) {
  const ext = record.extensions ?? {};
  const binding = ext.earworm_observation;
  const context = ext.earworm_matter_context;
  if (!binding) return record.record_kind === 'observation_account' ? ['Observation account requires its binding'] : context ? ['Matter context currently requires an observation account binding'] : [];
  const errors = [];
  if (record.record_kind !== 'observation_account') errors.push('Observation binding requires observation_account record_kind');
  if (record.audio !== undefined) errors.push('Structured observation account cannot assert an audio asset');
  if (!context) return [...errors,'Observation account requires matter context'];
  const wrapped = record.listening?.[binding.mapping_namespace];
  const mapping = wrapped?.payload;
  if (wrapped?.contract !== MAPPING || !object(mapping) || mapping.contract !== MAPPING || !object(mapping.report) || !object(mapping.source_snapshot)) return [...errors,'Unresolved retained observation mapping'];
  const source = mapping.source_snapshot;
  const report = mapping.report;
  if (!Array.isArray(source.observations) || !Array.isArray(report.features)) return [...errors,'Malformed retained observation/report scope'];
  for (const [actual,expected] of [[binding.mapping_ref,mapping.mapping_id],[binding.source_record_ref,mapping.source_record_ref],[binding.source_record_ref,source.id],[binding.observation_ref,mapping.source_observation_ref],[binding.observation_ref,report.subject_ref],[binding.report_ref,report.report_id],[context.subject_ref,binding.observation_ref],[record.subject,binding.observation_ref]]) {
    if (typeof actual !== 'string' || actual !== expected) errors.push('Observation binding identity mismatch');
  }
  if (report.contract !== 'akouo/agent-report/v0.1' || mapping.attribution !== 'retained_source' || mapping.execution !== 'not_requested') errors.push('Observation mapping must preserve source attribution and non-execution');
  const listening = record.auditum?.listenings?.find(item=>item.listening_id === binding.listening_ref);
  if (!listening || listening.listener_type !== 'agent' || listening.listener_id !== report.listener_id || listening.listening_pass_ref !== report.listening_pass_id || listening.report_namespace !== binding.mapping_namespace || listening.contract !== MAPPING) errors.push('Observation receiving pass is not bound to its mapping');
  const decision = record.auditum?.route_decisions?.find(item=>listening?.route_decision_refs?.includes(item.decision_id));
  if (!decision || decision.outcome !== 'proceed' || decision.subject !== binding.observation_ref || decision.authority.actor !== report.listener_id || decision.listening_id !== binding.listening_ref) errors.push('Observation account requires a bound successful receiving-route decision');
  for (const feature of report.features) {
    if (!object(feature) || feature.category !== 'undetermined' || feature.claim?.source !== 'provider' || feature.claim?.listening_pass_id !== report.listening_pass_id) errors.push('Retained observation is not the receiving agent\'s own measurement');
  }
  const access = ext.earworm_listening_access;
  if (report.apparatus_ref !== access?.declaration_id) errors.push('Observation report access mismatch');
  errors.push(...matterContextErrors(context,source,access));
  if (!ext.earworm_listening_context) errors.push('Observation account requires listening context');
  else {
    const contextErrors = listeningContextErrors(ext.earworm_listening_context,record);
    errors.push(...contextErrors);
    if (!contextErrors.length) {
      const reportContext = ext.earworm_listening_context.contexts.find(item=>item.listening_ref === binding.listening_ref);
      if (reportContext?.report?.ref !== report.report_id || !same(reportContext?.recipients,report.recipients)) errors.push('Listening context must preserve report identity and recipients');
    }
  }
  try {
    if (parseContractInstant(record.created_at) < parseContractInstant(listening?.created_at) || parseContractInstant(listening?.created_at) < parseContractInstant(decision?.decided_at)) errors.push('Observation listening/route chronology is inconsistent');
    if (parseContractInstant(record.created_at) < parseContractInstant(decision?.decided_at)) errors.push('Observation account predates its route decision');
  } catch { errors.push('Observation route chronology is unavailable'); }
  return errors;
}

export function observationAccountErrors(record, validateMapping) {
  const errors = nextRecordErrors(record);
  if (errors.length) return errors;
  if (record.record_kind !== 'observation_account') return ['Expected an observation account'];
  const binding = record.extensions.earworm_observation;
  return callbackErrors(validateMapping,record.listening[binding.mapping_namespace].payload);
}

/** Build a new account using an explicitly supplied route decision and foreign validator. */
export function createObservationAccount(mapping, options, validateMapping) {
  assertSupportedContracts(['earworm/akousma/v1.7','earworm/auditum/v3',OBSERVATION_ACCOUNT_CONTRACT,MATTER_CONTEXT_CONTRACT,MAPPING,'earworm/listening-access/v1','earworm/listening-context/v1'],options.supported_contracts);
  const external = callbackErrors(validateMapping,mapping);
  if (external.length) throw new Error(external.join('; '));
  for (const key of ['akousma_id','created_at','originating_app','listening_id','matter_context_id']) if (typeof options[key] !== 'string' || !options[key].trim()) throw new TypeError(`Missing account option: ${key}`);
  const source = mapping.source_snapshot, report = mapping.report;
  const identities = [options.akousma_id,options.listening_id,options.matter_context_id];
  if (new Set(identities).size !== identities.length || identities.some(id=>[source.id,mapping.mapping_id,report.report_id,report.listening_pass_id].includes(id))) throw new Error('Observation account requires fresh record/context/listening identities');
  const decision = structuredClone(options.route_decision);
  const context = {contract:MATTER_CONTEXT_CONTRACT,context_id:options.matter_context_id,vocabulary:'masa/0.2.0',source_record_ref:source.id,subject_ref:report.subject_ref,registers:structuredClone(source.registers),scales:structuredClone(source.scales),source_modality:structuredClone(options.source_modality),representation:structuredClone(options.representation),access_declaration_ref:report.apparatus_ref,temporal_scope:structuredClone(options.temporal_scope)};
  const unknown = reason=>({status:'unknown',reason});
  const result = {
    akousma_id:options.akousma_id,schema_version:'1.7.0',record_kind:'observation_account',created_at:options.created_at,subject:report.subject_ref,
    provenance:{source_type:'unknown',origin:'unknown',originating_app:options.originating_app,created_at:options.created_at},
    lineage:{parent_akousma_ids:[]},listening:{[NAMESPACE]:{contract:MAPPING,payload:structuredClone(mapping)}},tags:[],annotations:{},
    auditum:{contract:'earworm/auditum/v3',listenings:[{listening_id:options.listening_id,listener_id:report.listener_id,listener_type:'agent',created_at:options.created_at,report_namespace:NAMESPACE,contract:MAPPING,listening_pass_ref:report.listening_pass_id,route_decision_refs:[decision.decision_id]}],route_decisions:[decision],actions:[],disagreements:[],honest_absences:[]},
    extensions:{earworm_observation:{contract:OBSERVATION_ACCOUNT_CONTRACT,mapping_namespace:NAMESPACE,mapping_ref:mapping.mapping_id,source_record_ref:source.id,observation_ref:report.subject_ref,report_ref:report.report_id,listening_ref:options.listening_id,relation:'retained_observation_report',execution:'not_requested'},earworm_matter_context:context,earworm_listening_access:structuredClone(options.access),earworm_listening_context:{contract:'earworm/listening-context/v1',contexts:[{listening_ref:options.listening_id,subject_ref:report.subject_ref,recipients:structuredClone(report.recipients),access_declaration_ref:report.apparatus_ref,report:{ref:report.report_id,contract:MAPPING,format:'structured',readability:{status:'known',value:'machine_readable'},human_rendering:{status:'none',reason:'This binding creates no human rendering.'}},renderings:[]}],claims:report.features.map(feature=>({claim_ref:feature.claim.claim_id,listening_ref:options.listening_id,validity:unknown('No receiving-claim validity policy supplied.'),retention:unknown('No receiving-claim retention policy supplied.')}))}}
  };
  const errors = nextRecordErrors(result);
  if (errors.length) throw new Error(errors.join('; '));
  return result;
}
