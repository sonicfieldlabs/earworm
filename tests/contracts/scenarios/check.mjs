/* Test orchestration only: validators are supplied by the source or packed SDK. */
import assert from 'node:assert/strict';

export function checkListeningScenarios(sdk, legacyValid, matrix) {
  assert.equal(matrix.contract,'earworm/listening-scenarios/v1');
  assert.equal(matrix.evidence_class,'synthetic_contract_fixture');
  assert.equal(matrix.execution,'not_requested');
  assert.deepEqual(matrix.rows.map(row=>row.id),[
    'agent_only','human_agent','influenced_ensemble','second_report','beyond_band','generation_lineage']);
  assert.equal(matrix.negative_cases.length,13);
  assert.equal(new Set(matrix.negative_cases.map(item=>item.name)).size,13);
  const before=JSON.stringify(matrix);
  const result={scenarios:[],negatives:[]};
  for (const row of matrix.rows) {
    const {record}=row;
    assert.deepEqual(sdk.akousmaShapeErrors(record),[],row.id);
    assert.equal(legacyValid(record),row.legacy_schema_valid,`${row.id}: legacy reader`);
    assert.deepEqual(JSON.parse(JSON.stringify(record)),record);
    if (record.schema_version==='1.7.0') assert.deepEqual(sdk.nextRecordReferenceErrors(record,row.scope),[],row.id);
    const ext=record.extensions;
    if (ext.earworm_listening_access) assert.deepEqual(sdk.listeningAccessErrors(ext.earworm_listening_access),[],row.id);
    if (ext.earworm_listening_context) assert.deepEqual(sdk.listeningContextErrors(ext.earworm_listening_context,record),[],row.id);
    if (row.adapter) {
      const mapped=sdk.adaptListeningPasses(row.adapter);
      assert.deepEqual(mapped,ext.akouo_pass_adapter,row.id);
      assert.deepEqual(mapped.listenings,record.auditum.listenings);
      assert.deepEqual(mapped.ensemble,record.auditum.ensemble);
      assert.equal(mapped.ensemble.influence_edges.length,row.id==='influenced_ensemble'?1:0);
      assert.deepEqual(record.auditum.listenings.map(l=>l.listener_type),['agent','human']);
    }
    result.scenarios.push({id:row.id,legacy_schema_valid:row.legacy_schema_valid,valid:true});
  }
  for (const item of matrix.negative_cases) {
    const row=structuredClone(matrix.rows.find(row=>row.id===item.scenario));
    if (!item.path.length) row[item.target]=structuredClone(item.value);
    else {
      let target=row[item.target];
      for (const key of item.path.slice(0,-1)) target=target[key];
      target[item.path.at(-1)]=structuredClone(item.value);
    }
    const validators={
      record:()=>sdk.akousmaShapeErrors(row.record),
      access:()=>sdk.listeningAccessErrors(row.record.extensions.earworm_listening_access),
      context:()=>sdk.listeningContextErrors(row.record.extensions.earworm_listening_context,row.record),
      references:()=>sdk.nextRecordReferenceErrors(row.record,row.scope),
    };
    if (item.validator==='adapter') assert.throws(()=>sdk.adaptListeningPasses(row.adapter),undefined,item.name);
    else assert.ok(validators[item.validator]().length,item.name);
    result.negatives.push({name:item.name,rejected:true});
  }
  assert.equal(JSON.stringify(matrix),before,'Validation changed retained source fixtures');
  return result;
}
