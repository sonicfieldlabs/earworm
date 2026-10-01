import json
import unittest
from copy import deepcopy
from pathlib import Path
from akousma.transformation_graph import create_transformation_graph, transformation_graph_errors
import akousma

ROOT = Path(__file__).resolve().parents[3]
def read(name):
    return json.loads((ROOT / f'tests/contracts/graphs/{name}.json').read_text())


class TransformationGraphTest(unittest.TestCase):
    def setUp(self):
        self.f = read('processing')
        # Unit boundary stub only; installed integration smoke uses actual MASA validation.
        self.adapter = dict(validate_masa=lambda _: [], lineage_directions=self.f['lineage_directions'])

    def test_shared_graph_and_detached_evidence(self):
        before = deepcopy(self.f)
        graph = create_transformation_graph(self.f['source'], self.f['options'], **self.adapter)
        self.assertEqual(graph, self.f['expected'])
        self.assertEqual(transformation_graph_errors(graph, **self.adapter), [])
        graph['source_record']['extensions']['example:roundtrip']['deep']['values'].append('changed')
        self.assertEqual(self.f, before)

    def test_shared_negative_vectors(self):
        for row in read('cases'):
            with self.subTest(row['name']):
                graph = deepcopy(self.f['expected']); target = graph
                for key in row['path'][:-1]:
                    target = target[key]
                target[row['path'][-1]] = row['value']
                self.assertTrue(transformation_graph_errors(graph, **self.adapter))

    def test_inverse_relation_direction(self):
        source = deepcopy(self.f['source']); relation = source['relations'][0]
        relation['subject'], relation['object'] = relation['object'], relation['subject']
        relation['predicate'] = 'masa:derivation-of'
        graph = create_transformation_graph(source, self.f['options'], **self.adapter)
        self.assertEqual(graph['edges'], self.f['expected']['edges'])

    def test_refused_operation_has_receipt_and_no_graph_edge(self):
        source = deepcopy(self.f['source']); source['history']['events'][0].update(finalStatus='refused', outputs=[]); source['relations'] = []
        graph = create_transformation_graph(source, self.f['options'], **self.adapter)
        self.assertEqual(graph['edges'], [])
        self.assertEqual(len(graph['operation_refs']), 1)

    def test_negotiation_and_foreign_validation_required(self):
        with self.assertRaises(ValueError):
            create_transformation_graph(self.f['source'], {**self.f['options'], 'supported_contracts': []}, **self.adapter)
        with self.assertRaisesRegex(ValueError, 'invalid policy'):
            create_transformation_graph(self.f['source'], self.f['options'], **{**self.adapter, 'validate_masa': lambda _: ['invalid policy']})
        with self.assertRaises(TypeError):
            transformation_graph_errors(self.f['expected'], **{**self.adapter, 'validate_masa': lambda _: False})

    def test_foreign_validator_cannot_mutate_retained_source(self):
        def mutate(record):
            record['title'] = 'changed'
            return []
        graph = create_transformation_graph(self.f['source'], self.f['options'], **{**self.adapter, 'validate_masa': mutate})
        self.assertEqual(graph, self.f['expected'])

    def test_bundled_schema_and_nonfinite_json(self):
        self.assertEqual((ROOT / 'packages/core/schemas/transformation-graph.schema.json').read_bytes(),
                         (Path(akousma.__file__).parent / 'transformation-graph.schema.json').read_bytes())
        graph = deepcopy(self.f['expected']); graph['source_record']['extensions']['test:number'] = float('nan')
        self.assertTrue(transformation_graph_errors(graph, **self.adapter))
