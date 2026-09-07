import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import akousma
from akousma.agent_sectors import create_measurement_set,measurement_set_errors,agent_sector_view,compare_measurement_descriptors
from akousma.record_evolution import next_record_errors,next_record_reference_errors
ROOT=Path(__file__).resolve().parents[3]
def read(name):return json.loads((ROOT/f'tests/contracts/sectors/{name}.json').read_text())

class AgentSectorTest(unittest.TestCase):
    def setUp(self):self.fixture=read('comparison')

    def test_shared_comparison_and_view_parity(self):
        f=self.fixture;before=deepcopy(f)
        self.assertEqual(compare_measurement_descriptors(f['left'],f['right'],f['options']),f['expected'])
        self.assertEqual(agent_sector_view(f['left'],'sector:descriptors'),read('view'))
        view=agent_sector_view(f['left'],'sector:descriptors');view['renderings'][0]['access']['value']='public'
        self.assertEqual(f,before)

    def test_shared_boundary_vectors(self):
        for row in read('cases'):
            with self.subTest(row['name']):
                record=deepcopy(read('observation') if row['base']=='observation' else self.fixture['left']);target=record
                for key in row['path'][:-1]:target=target[key]
                target[row['path'][-1]]=row['value']
                errors=next_record_reference_errors(record,[self.fixture['right']]) if row['scope'] else next_record_errors(record)
                self.assertEqual(not errors,row['valid'])

    def test_foreign_validation_negotiation_and_source_isolation(self):
        value=self.fixture['left']['extensions']['earworm_measurements'];before=deepcopy(value)
        produced=create_measurement_set([s['record'] for s in value['sources']],value['descriptors'],lambda _:[],['earworm/measurement-set/v1','masa/0.2.0'])
        self.assertEqual(produced,value)
        produced['sources'][0]['record']['extensions']['fixture:new']=['changed']
        self.assertEqual(value,before)
        self.assertEqual(measurement_set_errors(value,lambda _:['Invalid foreign source']),['Invalid foreign source'])
        with self.assertRaises(TypeError):measurement_set_errors(value,lambda _:False)
        with self.assertRaises(ValueError):create_measurement_set([],[],lambda _:[],[])

    def test_all_four_descriptor_comparisons(self):
        for feature in ['spectral_centroid','band_energy','level','duration']:
            options={**self.fixture['options'],'source_descriptor_ref':'descriptor:'+feature,'target_descriptor_ref':'descriptor:'+feature}
            relation=compare_measurement_descriptors(self.fixture['left'],self.fixture['right'],options)
            self.assertEqual(relation['criterion']['score']['value'],250 if feature=='spectral_centroid' else 0)
            self.assertEqual(relation['review']['status'],'unreviewed')
            self.assertEqual(relation['epistemic_status'],'inferred')

    def test_mismatched_or_unknown_method_cannot_be_compared(self):
        for change in ['version','window','parameters','metric']:
            right=deepcopy(self.fixture['right']);m=right['extensions']['earworm_measurements']['sources'][0]['record']['measurements'][0]
            if change=='version':m['method']['version']={'state':'unknown','reason':'Missing version'}
            elif change=='window':m['window']['end']=0.9
            elif change=='parameters':m['method']['parameters']={'weighting':'other'}
            else:m['metric']='different metric'
            with self.assertRaises(ValueError):compare_measurement_descriptors(self.fixture['left'],right,self.fixture['options'])

    def test_digital_and_perceptual_levels_are_not_implicitly_converted(self):
        right=deepcopy(self.fixture['right']);value=right['extensions']['earworm_measurements'];value['sources'][0]['record']['measurements'][2]['unit']='LUFS';value['descriptors'][2]['reference_basis']='perceptual_loudness'
        self.assertEqual(next_record_errors(right),[])
        options={**self.fixture['options'],'source_descriptor_ref':'descriptor:level','target_descriptor_ref':'descriptor:level'}
        with self.assertRaises(ValueError):compare_measurement_descriptors(self.fixture['left'],right,options)

    def test_physical_spl_requires_apparatus_and_calibration_declarations(self):
        value=deepcopy(self.fixture['left']['extensions']['earworm_measurements']);m=value['sources'][0]['record']['measurements'][2];m['unit']='dB_SPL';value['descriptors'][2]['reference_basis']='sound_pressure'
        self.assertTrue(measurement_set_errors(value,lambda _:[]))
        m['method']['apparatusRefs']=['apparatus:fixture'];m['method']['parameters']={'calibration_ref':'calibration:fixture','reference_pressure_pa':0.00002}
        self.assertEqual(measurement_set_errors(value,lambda _:[]),[])

    def test_nonfinite_unknown_source_extension_rejected(self):
        value=deepcopy(self.fixture['left']['extensions']['earworm_measurements']);value['sources'][0]['record']['extensions']['fixture:nonfinite']=float('inf')
        self.assertTrue(measurement_set_errors(value,lambda _:[]))

    def test_store_retains_sectors_descriptors_and_comparison_after_reindex(self):
        left,right=self.fixture['left'],self.fixture['right']
        with TemporaryDirectory() as path:
            store=akousma.AkousmataStore(path)
            try:
                store.put(right);store.put(left)
                for kind in ['measurement','sector','rendering','relation']:
                    changed=deepcopy(left)
                    if kind=='measurement':changed['extensions']['earworm_measurements']['sources'][0]['record']['extensions']['fixture:edit']='changed'
                    elif kind=='sector':changed['extensions']['earworm_agent_sector']['entries'][0]['renderings']=[]
                    elif kind=='rendering':changed['extensions']['earworm_listening_context']['contexts'][0]['renderings'][0]['access']['value']='public'
                    else:changed['lineage']['relations'][0]['criterion']['score']['value']=0
                    with self.assertRaises(ValueError):store.put(changed)
                store.reindex()
                self.assertEqual(store.get(left['akousma_id']),left)
                self.assertEqual(agent_sector_view(store.get(left['akousma_id']),'sector:descriptors'),read('view'))
                self.assertEqual(next_record_reference_errors(store.get(left['akousma_id']),[store.get(right['akousma_id'])]),[])
                self.assertEqual(store.relation_details(left['akousma_id']),left['lineage']['relations'])
                self.assertFalse(store.verify()['invalid_records'])
            finally:store.close()

    def test_rendering_from_another_listening_cannot_be_borrowed(self):
        record=deepcopy(self.fixture['left']);ctx=record['extensions']['earworm_listening_context'];other=deepcopy(ctx['contexts'][0]);other['listening_ref']='listening:other';other['renderings'][0]['rendering_id']='rendering:other';other['report']['human_rendering']['rendering_refs']=['rendering:other'];ctx['contexts'].append(other)
        listening=deepcopy(record['auditum']['listenings'][0]);listening['listening_id']='listening:other';record['auditum']['listenings'].append(listening)
        record['extensions']['earworm_agent_sector']['entries'][0]['renderings']=['rendering:other']
        errors=next_record_errors(record)
        self.assertTrue(any('own listening' in error for error in errors),errors)
