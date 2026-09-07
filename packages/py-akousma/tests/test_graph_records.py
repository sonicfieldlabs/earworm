import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import akousma
from akousma.graph_records import create_graph_record, revise_graph_record, graph_revision_errors
from akousma.record_evolution import next_record_errors, next_record_reference_errors
from akousma.transposition_recipes import transposition_recipe_errors
from akousma.transformation_graph import create_transformation_graph

ROOT = Path(__file__).resolve().parents[3]
def read(path):
    return json.loads((ROOT/path).read_text())

class GraphRecordTest(unittest.TestCase):
    def setUp(self):
        self.f = read('tests/contracts/graphs/processing.json')
        self.g = read('tests/contracts/graphs/records.json')
        # Unit stub only; actual MASA source-policy/direction checks run in installed smoke.
        self.adapter = dict(validate_masa=lambda _: [], lineage_directions=self.f['lineage_directions'])

    def test_shared_constructors_and_scope(self):
        before = deepcopy(self.g)
        self.assertEqual(create_graph_record(self.f['expected'], self.g['options'], **self.adapter), self.g['record'])
        self.assertEqual(revise_graph_record(self.g['record'], self.g['revisionOptions'], **self.adapter), self.g['revised'])
        self.assertEqual(next_record_reference_errors(self.g['revised'], [self.g['record']]), [])
        self.assertTrue(next_record_reference_errors(self.g['revised'], []))
        self.assertEqual(self.g, before)

    def test_monotonic_revision_source_identity_and_time(self):
        for kind in ['skip', 'rewrite_source', 'backdate', 'other_family']:
            r = deepcopy(self.g['revised']); graph = r['extensions']['earworm_transformation_graph']
            if kind == 'skip': graph['revision'] = 4
            if kind == 'rewrite_source': graph['source_record']['title'] = 'rewritten'
            if kind == 'backdate': r['created_at'] = '2020-01-01T00:00:00Z'
            if kind == 'other_family': graph['graph_id'] = 'other'
            with self.subTest(kind=kind): self.assertTrue(graph_revision_errors(r, self.g['record']))
        with self.assertRaises(ValueError):
            revise_graph_record(self.g['record'], {**self.g['revisionOptions'], 'akousma_id': self.g['record']['akousma_id']}, **self.adapter)

    def test_store_requires_foreign_validator_and_protects_whole_graph(self):
        with TemporaryDirectory() as path:
            store = akousma.AkousmataStore(path)
            try:
                with self.assertRaises(TypeError): store.put(self.g['record'])
                with self.assertRaises(ValueError): store.put(self.g['record'], **{**self.adapter, 'validate_masa': lambda _: ['invalid policy']})
                self.assertIsNone(store.get(self.g['record']['akousma_id']))
                store.put(self.g['record'], **self.adapter)
                for kind in ['rewrite', 'remove', 'nodes']:
                    r = deepcopy(self.g['record'])
                    if kind == 'rewrite': r['extensions']['earworm_transformation_graph']['source_record']['title'] = 'rewritten'
                    if kind == 'remove': del r['extensions']['earworm_transformation_graph']
                    if kind == 'nodes': r['extensions']['earworm_transformation_graph']['nodes'][0]['node_id'] = 'other'
                    with self.subTest(kind=kind), self.assertRaises(ValueError): store.put(r, **self.adapter)
                self.assertEqual(store.get(self.g['record']['akousma_id']), self.g['record'])
            finally: store.close()

    def test_revision_reopen_reindex_and_explicit_branches(self):
        with TemporaryDirectory() as path:
            store = akousma.AkousmataStore(path)
            try:
                store.put(self.g['record'], **self.adapter)
                store.put(self.g['revised'], **self.adapter)
                self.assertEqual(len(store.revision_chain(self.g['record']['akousma_id'])), 2)
                branch = revise_graph_record(self.g['record'], {**self.g['revisionOptions'], 'akousma_id': 'graph:branch', 'revision_id': 'revision:branch'}, **self.adapter)
                store.put(branch, **self.adapter)
                self.assertEqual(len(store.revision_heads(self.g['record']['akousma_id'])), 2)
                with self.assertRaises(ValueError): store.current_head(self.g['record']['akousma_id'])
                store.reindex()
                self.assertEqual(store.get(self.g['revised']['akousma_id']), self.g['revised'])
                self.assertFalse(store.verify()['invalid_records'])
            finally: store.close()
            reopened = akousma.AkousmataStore(path)
            try: self.assertEqual(len(reopened.revision_heads(self.g['record']['akousma_id'])), 2)
            finally: reopened.close()

    def test_missing_parent_skipped_revision_and_duplicate_root_rejected(self):
        with TemporaryDirectory() as path:
            store = akousma.AkousmataStore(path)
            try:
                with self.assertRaises(ValueError): store.put(self.g['revised'], **self.adapter)
                store.put(self.g['record'], **self.adapter)
                skipped = deepcopy(self.g['revised']); skipped['extensions']['earworm_transformation_graph']['revision'] = 4
                with self.assertRaises(ValueError): store.put(skipped, **self.adapter)
                duplicate = deepcopy(self.g['record']); duplicate['akousma_id'] = 'unrelated-root'
                with self.assertRaises(ValueError): store.put(duplicate, **self.adapter)
                store.forget(self.g['record']['akousma_id'])
                with self.assertRaises(ValueError): store.put(self.g['record'], **self.adapter)
            finally: store.close()

    def test_verify_reports_raw_revision_corruption(self):
        with TemporaryDirectory() as path:
            store = akousma.AkousmataStore(path)
            try:
                store.put(self.g['record'], **self.adapter); store.put(self.g['revised'], **self.adapter)
                bad = deepcopy(self.g['revised']); bad['extensions']['earworm_transformation_graph']['revision'] = 7
                store.conn.execute('UPDATE akousmata SET record=? WHERE akousma_id=?', (json.dumps(bad), bad['akousma_id'])); store.conn.commit()
                self.assertTrue(store.verify()['invalid_records'])
            finally: store.close()

    def test_shared_four_recipes_and_negative_vectors(self):
        sources = read('tests/contracts/recipes/sources.json')
        for row in sources:
            self.assertEqual(transposition_recipe_errors(row['source']), [])
            self.assertEqual(create_transformation_graph(row['source'], row['options'], **self.adapter)['source_record'], row['source'])
        for row in read('tests/contracts/recipes/cases.json'):
            source = deepcopy(sources[row['base']]['source']); target = source
            for key in row['path'][:-1]: target = target[key]
            target[row['path'][-1]] = row['value']
            with self.subTest(row['name']):
                self.assertTrue(transposition_recipe_errors(source))
                with self.assertRaises(ValueError): create_transformation_graph(source, sources[row['base']]['options'], **self.adapter)

    def test_pitch_duration_is_declared_independently(self):
        source = read('tests/contracts/recipes/sources.json')[3]['source']
        source['representations'][1]['audio']['durationSeconds']['value'] = .75
        source['history']['events'][0]['extensions']['earworm:transposition']['duration_behavior'] = 'changed'
        self.assertEqual(transposition_recipe_errors(source), [])

    def test_recipe_schema_bundled_and_known_hash_shape(self):
        self.assertEqual((ROOT/'packages/core/schemas/transposition-recipe.schema.json').read_bytes(), (Path(akousma.__file__).parent/'transposition-recipe.schema.json').read_bytes())
        source = read('tests/contracts/recipes/sources.json')[0]['source']
        source['representations'][0]['integrity'] = dict(state='known', value=dict(sha256='0'*64))
        self.assertEqual(transposition_recipe_errors(source), [])

    def test_recipe_negotiation_and_safe_revision_integer(self):
        row = read('tests/contracts/recipes/sources.json')[0]
        with self.assertRaises(ValueError):
            create_transformation_graph(row['source'], {**row['options'], 'supported_contracts': ['earworm/transformation-graph/v1', 'masa/0.2.0']}, **self.adapter)
        graph = deepcopy(self.f['expected']); graph['revision'] = 9007199254740992
        with self.assertRaises(ValueError): create_graph_record(graph, self.g['options'], **self.adapter)
