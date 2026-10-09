/* Synthetic fixtures composed from retained local examples; no audio execution. */
import assert from 'node:assert/strict';
import { readFileSync, writeFileSync, mkdirSync } from 'node:fs';
import { adaptListeningPasses } from '../packages/sdk-js/src/listening-contracts.js';

const root = new URL('../', import.meta.url);
const read = path => JSON.parse(readFileSync(new URL(path, root), 'utf8'));
const clone = structuredClone;
const template = read('tests/contracts/evolution/report.json');
const scope = read('tests/contracts/evolution/scope.json');
const access = read('packages/core/fixtures/synthetic-wideband.listening-access.json');
const human = read('tests/fixtures/human-context.akousma.json');
const adapter = read('tests/contracts/pass-adapter.json').input;
const rows = [];

function unknownFeature(pass) {
  return { feature_id:'feature:scenario-unknown', namespace:'fixture.scenario', name:'unestablished-access',
    category:'undetermined', value:{status:'unknown',reason:'Synthetic metadata; no physical, model or human evaluation ran.'},
    claim:{claim_id:'claim:scenario-unknown',statement:'No new physical measurement or embodied hearing is established.',
      confidence:'undetermined',source:'model',evidence_refs:['repr:16k'],listening_pass_id:pass,actionability:'informational'} };
}

function agentRecord(id) {
  const record = clone(template);
  record.akousma_id = `ak_scenario_${id}`;
  record.schema_version = '1.6.0';
  record.auditum.contract = 'earworm/auditum/v2';
  record.subject = access.subject_ref;
  record.lineage = {parent_akousma_ids:[]};
  record.tags = ['synthetic','scenario',id];
  record.summary = 'Synthetic structured agent account; no embodied hearing asserted.';
  record.extensions.earworm_listening_access = clone(access);
  record.extensions['fixture:opaque'] = {future:[false,0,null,{preserve:'source'}]};
  const report = record.listening['agent.report'].payload;
  Object.assign(report,{report_id:`report:${id}`,listening_pass_id:`pass:${id}`,subject_ref:access.subject_ref,
    apparatus_ref:access.declaration_id,input_refs:['repr:16k'],report_of_refs:[],features:[unknownFeature(`pass:${id}`)]});
  const listening = record.auditum.listenings[0];
  Object.assign(listening,{listening_id:`listening:${id}`,listening_pass_ref:`pass:${id}`,note:'Synthetic agent pass.'});
  const context = record.extensions.earworm_listening_context;
  Object.assign(context.contexts[0],{listening_ref:listening.listening_id,subject_ref:access.subject_ref,
    access_declaration_ref:access.declaration_id});
  context.contexts[0].report.ref = report.report_id;
  Object.assign(context.claims[0],{claim_ref:report.features[0].claim.claim_id,listening_ref:listening.listening_id});
  record.auditum.honest_absences[0].listening_id = listening.listening_id;
  Object.assign(record.auditum.route_decisions[0],{decision_id:`decision:${id}`,gate:'inference',
    subject:access.subject_ref,listening_id:listening.listening_id,reason:'Synthetic fixture account only.'});
  return record;
}

function routeFor(record, profile='agent') {
  const report = record.listening['agent.report'].payload;
  const declaration = record.extensions.earworm_listening_access;
  const resolved = new Set([report.subject_ref,...report.input_refs,...report.report_of_refs,report.apparatus_ref,
    ...report.recipients.map(r=>r.id)]);
  for (const axis of ['sampled_representation','model_input']) {
    const value = declaration[axis];
    if (value.status === 'known') {
      resolved.add(value.representation_ref);
      for (const ref of [...value.evidence_refs,...(value.preprocessing_refs ?? [])]) resolved.add(ref);
    }
  }
  const request = {contract:'akouo/agent-route/v0.1',request_id:`route:${record.akousma_id}`,profile,
    supported_contracts:['akouo/companions/v0.1','akouo/agent-route/v0.1','akouo/agent-report/v0.1',
      'earworm/listening-access/v1','akouo/extended-spectrum-request/v0.1'],
    relation:{of:profile==='second_report'?'record':'representation',ref:report.subject_ref},
    resolved_refs:[...resolved],requested_categories:[...new Set(report.features.map(f=>f.category))]};
  for (const field of ['report_id','listening_pass_id','listener_id','input_refs','apparatus_ref','recipients','report_of_refs']) {
    request[field]=clone(report[field]);
  }
  return {request,expected_outcome:'proceed',expected_measured_allowed:false};
}

const agent = agentRecord('agent_only');
rows.push({id:'agent_only',record:agent,scope:[],legacy_schema_valid:true,route:routeFor(agent)});

for (const influenced of [false,true]) {
  const id = influenced?'influenced_ensemble':'human_agent';
  const record = agentRecord(id);
  const input = clone(adapter);
  input.bindings[0].report_namespace='agent.report';
  input.bindings[0].contract='akouo/agent-report/v0.1';
  input.bindings[1].report_namespace='human.note';
  if (!influenced) {
    input.passes[1].influenced_by=[];
    input.ensemble.kind='plural_listening';
    input.ensemble.influence_edges=[];
  }
  const mapped=adaptListeningPasses(input);
  const report=record.listening['agent.report'].payload;
  report.listening_pass_id=input.passes[0].id;
  report.features[0].claim.listening_pass_id=report.listening_pass_id;
  record.listening['human.note']=clone(human.listening['human.note']);
  record.auditum.listenings=clone(mapped.listenings);
  record.auditum.ensemble=clone(mapped.ensemble);
  record.extensions.akouo_pass_adapter=clone(mapped);
  const context=record.extensions.earworm_listening_context;
  context.contexts[0].listening_ref=mapped.listenings[0].listening_id;
  context.claims[0].listening_ref=mapped.listenings[0].listening_id;
  const humanContext=clone(human.extensions.earworm_listening_context.contexts[0]);
  humanContext.listening_ref=mapped.listenings[1].listening_id;
  context.contexts.push(humanContext);
  context.access_declarations=[clone(human.extensions.earworm_listening_access)];
  record.auditum.honest_absences[0].listening_id=mapped.listenings[0].listening_id;
  record.auditum.route_decisions[0].listening_id=mapped.listenings[0].listening_id;
  rows.push({id,record,scope:[],legacy_schema_valid:true,adapter:input,route:routeFor(record)});
}

const second=clone(template);
second.akousma_id='ak_scenario_second_report';
const secondReport=second.listening['agent.report'].payload;
const unknown=unknownFeature(secondReport.listening_pass_id);
unknown.claim.evidence_refs=clone(secondReport.report_of_refs);
secondReport.features.push(unknown);
const claim=clone(second.extensions.earworm_listening_context.claims[0]);
claim.claim_ref=unknown.claim.claim_id;
second.extensions.earworm_listening_context.claims.push(claim);
rows.push({id:'second_report',record:second,scope:clone(scope),legacy_schema_valid:false,route:routeFor(second,'second_report')});

const beyond=agentRecord('beyond_band');
const beyondRoute=routeFor(beyond,'beyond');
beyondRoute.expected_spectral_support='unsupported';
beyondRoute.spectral_request={contract:'akouo/extended-spectrum-request/v0.1',request_id:'spectral:scenario',
  subject_ref:access.subject_ref,band_hz:{lower:20000,upper:30000},window_s:{start:0,end:10},
  channel_count:1,claim_kind:'spectral_measurement',resolved_refs:clone(beyondRoute.request.resolved_refs),
  preprocessing:[{receipt_ref:'receipt:filtered-resample',kind:'filtered_resample',input_ref:'repr:96k',output_ref:'repr:16k'}]};
rows.push({id:'beyond_band',record:beyond,scope:[],legacy_schema_valid:true,route:beyondRoute});
rows.push({id:'generation_lineage',record:read('tests/contracts/evolution/decision.json'),scope:clone(scope),legacy_schema_valid:false});

const matrix={contract:'earworm/listening-scenarios/v1',status:'unreleased',evidence_class:'synthetic_contract_fixture',
  execution:'not_requested',rows,negative_cases:read('tests/contracts/scenarios/cases.json')};
assert.equal(new Set(rows.map(row=>row.id)).size,6);
const path=new URL('packages/core/fixtures/scenarios/matrix.json',root);
const content=JSON.stringify(matrix,null,2)+'\n';
if (process.argv.includes('--check')) {
  assert.equal(readFileSync(path,'utf8'),content,'Scenario bundle drift: run node scripts/generate-listening-scenarios.mjs');
  console.log('scenario generation: six canonical compositions match the portable bundle');
} else {
  mkdirSync(new URL('./',path),{recursive:true});writeFileSync(path,content);
  console.log('Wrote six synthetic listening scenarios from existing local contracts');
}
