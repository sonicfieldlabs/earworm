"""Shared matrix exercises installed readers and the actual temporary store."""
import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from jsonschema import Draft7Validator
import akousma
from akousma.listening_contracts import listening_access_errors, adapt_listening_passes
from akousma.listening_context import listening_context_errors
from akousma.record_evolution import next_record_reference_errors

ROOT=Path(__file__).resolve().parents[3]
MATRIX=ROOT/'packages/core/fixtures/scenarios/matrix.json'


def check_scenarios(matrix):
    before=deepcopy(matrix)
    assert matrix['contract']=='earworm/listening-scenarios/v1'
    assert matrix['evidence_class']=='synthetic_contract_fixture'
    assert matrix['execution']=='not_requested'
    assert [r['id'] for r in matrix['rows']]==[
        'agent_only','human_agent','influenced_ensemble','second_report','beyond_band','generation_lineage']
    assert len(matrix['negative_cases'])==len({item['name'] for item in matrix['negative_cases']})==13
    legacy=Draft7Validator(akousma.load_schema())
    result=dict(scenarios=[],negatives=[])
    for row in matrix['rows']:
        record=row['record'];ext=record['extensions']
        assert not akousma.validation_errors(record), (row['id'],akousma.validation_errors(record))
        assert legacy.is_valid(record)==row['legacy_schema_valid'],row['id']
        assert json.loads(json.dumps(record))==record
        if record['schema_version']=='1.7.0':
            assert not next_record_reference_errors(record,row['scope']),row['id']
        if 'earworm_listening_access' in ext:
            assert not listening_access_errors(ext['earworm_listening_access']),row['id']
        if 'earworm_listening_context' in ext:
            assert not listening_context_errors(ext['earworm_listening_context'],record),row['id']
        if 'adapter' in row:
            mapped=adapt_listening_passes(**row['adapter'])
            assert mapped==ext['akouo_pass_adapter'],row['id']
            assert mapped['listenings']==record['auditum']['listenings']
            assert mapped['ensemble']==record['auditum']['ensemble']
            assert len(mapped['ensemble']['influence_edges'])==(1 if row['id']=='influenced_ensemble' else 0)
            assert [item['listener_type'] for item in record['auditum']['listenings']]==['agent','human']
        result['scenarios'].append(dict(id=row['id'],legacy_schema_valid=row['legacy_schema_valid'],valid=True))
    for item in matrix['negative_cases']:
        row=deepcopy(next(row for row in matrix['rows'] if row['id']==item['scenario']))
        if not item['path']:row[item['target']]=deepcopy(item['value'])
        else:
            target=row[item['target']]
            for key in item['path'][:-1]:target=target[key]
            target[item['path'][-1]]=deepcopy(item['value'])
        validators=dict(record=lambda:akousma.validation_errors(row['record']),
            access=lambda:listening_access_errors(row['record']['extensions']['earworm_listening_access']),
            context=lambda:listening_context_errors(row['record']['extensions']['earworm_listening_context'],row['record']),
            references=lambda:next_record_reference_errors(row['record'],row['scope']))
        if item['validator']=='adapter':
            try:adapt_listening_passes(**row['adapter'])
            except (ValueError,TypeError):pass
            else:raise AssertionError(item['name'])
        else:assert validators[item['validator']](),item['name']
        result['negatives'].append(dict(name=item['name'],rejected=True))
    assert matrix==before,'Validation changed retained source fixtures'
    return result


class ListeningScenarioTest(unittest.TestCase):
    def test_shared_matrix(self):
        check_scenarios(json.loads(MATRIX.read_text()))

    def test_store_reopen_reindex_and_source_preservation(self):
        matrix=json.loads(MATRIX.read_text())
        for row in matrix['rows']:
            with self.subTest(scenario=row['id']),tempfile.TemporaryDirectory() as directory:
                store=akousma.AkousmataStore(directory)
                try:
                    for source in row['scope']:store.put(source)
                    store.put(row['record'])
                finally:store.close()
                store=akousma.AkousmataStore(directory)
                try:
                    store.reindex()
                    self.assertEqual(store.get(row['record']['akousma_id']),row['record'])
                    for source in row['scope']:self.assertEqual(store.get(source['akousma_id']),source)
                    self.assertEqual(store.verify()['invalid_records'],[])
                finally:store.close()


if __name__=='__main__':
    print(json.dumps(check_scenarios(json.loads(MATRIX.read_text()))))
