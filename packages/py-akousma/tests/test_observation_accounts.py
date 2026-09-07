import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import akousma
from akousma.observation_accounts import create_observation_account, observation_account_errors, matter_context_errors
from akousma.record_evolution import next_record_errors

ROOT=Path(__file__).resolve().parents[3]

def read(name): return json.loads((ROOT/f'tests/contracts/observations/{name}.json').read_text())

class ObservationAccountTest(unittest.TestCase):
    def setUp(self): self.fixture=read('account')

    def test_constructor_shared_parity_and_deep_source_isolation(self):
        before=deepcopy(self.fixture)
        record=create_observation_account(self.fixture['mapping'],self.fixture['options'],lambda _:[])
        self.assertEqual(record,self.fixture['expected'])
        record['listening']['akouo.observation']['payload']['source_snapshot']['extensions']['example:new']=['changed']
        self.assertEqual(self.fixture,before)

    def test_shared_negative_and_positive_vectors(self):
        for row in read('cases'):
            with self.subTest(row['name']):
                record=deepcopy(self.fixture['expected']);target=record
                for key in row['path'][:-1]:target=target[key]
                target[row['path'][-1]]=row['value']
                self.assertEqual(not next_record_errors(record),row['valid'])

    def test_external_validation_and_negotiation_are_explicit(self):
        record=self.fixture['expected']
        self.assertEqual(observation_account_errors(record,lambda _:[]),[])
        self.assertEqual(observation_account_errors(record,lambda _:['Invalid foreign source']),['Invalid foreign source'])
        with self.assertRaises(TypeError): observation_account_errors(record,lambda _:True)
        options=deepcopy(self.fixture['options']);options['supported_contracts']=[]
        with self.assertRaises(ValueError):create_observation_account(self.fixture['mapping'],options,lambda _:[])

    def test_new_identity_required(self):
        options=deepcopy(self.fixture['options']);options['akousma_id']=self.fixture['mapping']['report']['report_id']
        with self.assertRaises(ValueError):create_observation_account(self.fixture['mapping'],options,lambda _:[])

    def test_numerical_subsample_grid_is_not_physical_sensing(self):
        context=deepcopy(self.fixture['expected']['extensions']['earworm_matter_context']);source=self.fixture['mapping']['source_snapshot'];access=self.fixture['options']['access']
        context['temporal_scope']=dict(status='known',domain='mathematical_construction',window_s=dict(start=0,end=1),resolution_s=1/96000,sample_rate_hz=dict(status='known',value=48000),evidence_refs=['method:numerical-fixture'])
        self.assertEqual(matter_context_errors(context,source,access),[])
        for domain in ['physical_observation','sampled_representation']:
            context['temporal_scope']['domain']=domain
            self.assertTrue(matter_context_errors(context,source,access))
        context['temporal_scope']['domain']='mathematical_construction'
        for value in [0,-1,float('nan'),float('inf')]:
            context['temporal_scope']['resolution_s']=value
            self.assertTrue(matter_context_errors(context,source,access))

    def test_nonacoustic_physical_scope_needs_actual_method_apparatus(self):
        context=deepcopy(self.fixture['expected']['extensions']['earworm_matter_context']);source=deepcopy(self.fixture['mapping']['source_snapshot']);access=self.fixture['options']['access']
        context['temporal_scope']=dict(status='known',domain='physical_observation',window_s=dict(start=0,end=10),resolution_s=1,sample_rate_hz=dict(status='unknown',reason='Not a sampled audio representation.'),evidence_refs=['apparatus:fixture'])
        self.assertTrue(matter_context_errors(context,source,access))
        source['observations'][0]['method']['apparatusRefs']=['apparatus:fixture']
        self.assertEqual(matter_context_errors(context,source,access),[])

    def test_labels_preserve_namespaced_terms_without_implying_human_access(self):
        record=deepcopy(self.fixture['expected']);source=record['listening']['akouo.observation']['payload']['source_snapshot'];context=record['extensions']['earworm_matter_context']
        for key in ['registers','scales']:
            source[key].append('fixture:qualified');context[key].append('fixture:qualified')
        self.assertEqual(next_record_errors(record),[])
        self.assertEqual(record['extensions']['earworm_listening_access']['human_access'][0]['status'],'unknown')

    def test_store_protects_source_mapping_and_context_but_allows_curation(self):
        record=deepcopy(self.fixture['expected'])
        with TemporaryDirectory() as path:
            store=akousma.AkousmataStore(path)
            try:
                store.put(record)
                for target in ['source','context','binding','boolean']:
                    changed=deepcopy(record)
                    if target=='source':changed['listening']['akouo.observation']['payload']['source_snapshot']['extensions']['example:extra']='rewrite'
                    elif target=='context': changed['extensions']['earworm_matter_context']['source_modality']={'status':'unknown','reason':'Changed declaration'}
                    elif target=='binding':del changed['extensions']['earworm_observation']
                    else:
                        # Existing source metadata contains an integer revision; bool
                        # compares equal in Python but must not replace JSON evidence.
                        changed['listening']['akouo.observation']['payload']['source_snapshot']['revision']=True
                    with self.assertRaises(ValueError):store.put(changed)
                curated=deepcopy(record);curated['summary']='Curated local note';store.put(curated)
                store.reindex()
                self.assertEqual(store.get(record['akousma_id']),curated)
                self.assertFalse(store.verify()['invalid_records'])
            finally:store.close()

    def test_store_revision_preserves_original(self):
        record=deepcopy(self.fixture['expected']);revised=deepcopy(record)
        revised['akousma_id']='ak_observation_revision'
        revised['auditum']['revision']=dict(revision_id='revision:observation',revises_akousma_id=record['akousma_id'],reason='Qualified scope review',changes=['Retained updated interpretation of source modality.'],created_at=record['created_at'])
        revised['extensions']['earworm_matter_context']['source_modality']={'status':'unknown','reason':'Modality requires review.'}
        with TemporaryDirectory() as path:
            store=akousma.AkousmataStore(path)
            try:
                store.put(record);store.put(revised)
                self.assertEqual(store.get(record['akousma_id']),record)
                self.assertEqual(store.get(revised['akousma_id']),revised)
            finally:store.close()
