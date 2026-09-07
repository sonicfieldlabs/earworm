import json
import unittest
from copy import deepcopy
from pathlib import Path
from tempfile import TemporaryDirectory
import akousma
from akousma.auditum_view import auditum_view, forgetting_receipt_view, AUDITUM_VIEW_CONTRACT, FORGETTING_RECEIPT_CONTRACT

ROOT = Path(__file__).resolve().parents[3]
SUPPORTED = [AUDITUM_VIEW_CONTRACT, FORGETTING_RECEIPT_CONTRACT]


class AuditumViewTest(unittest.TestCase):
    def setUp(self):
        self.f = json.loads((ROOT / 'tests/contracts/views/auditum.json').read_text())
        self.calls = []
        def record(identifier):
            self.calls.append(identifier)
            return self.f['record'] if identifier == self.f['record']['akousma_id'] else self.f['available'] if identifier == 'ak_available' else None
        def receipt(identifier):
            self.calls.append(identifier)
            return self.f['receipt'] if identifier == 'ak_forgotten' else None
        self.options = dict(read_record=record, read_receipt=receipt, can_read=lambda i: i != 'ak_withheld', supported_contracts=SUPPORTED)

    def test_shared_view_and_permissions_before_lookup(self):
        self.assertEqual(auditum_view(self.f['record']['akousma_id'], **self.options), self.f['expected'])
        self.assertNotIn('ak_withheld', self.calls)
        self.calls.clear()
        self.assertEqual(auditum_view('ak_withheld', **self.options), dict(contract=AUDITUM_VIEW_CONTRACT, record_ref='ak_withheld', state='withheld'))
        self.assertEqual(self.calls, [])
        self.assertEqual(auditum_view('ak_missing', **self.options)['state'], 'unavailable')
        self.assertEqual(auditum_view('ak_forgotten', **self.options)['state'], 'forgotten')

    def test_detached_evidence_and_receipt_allowlist(self):
        before = deepcopy(self.f)
        view = auditum_view(self.f['record']['akousma_id'], **self.options)
        view['auditum']['listenings'].clear()
        self.assertEqual(self.f, before)
        self.assertNotIn('sensitive', json.dumps(forgetting_receipt_view(self.f['receipt'], 'ak_forgotten')))

    def test_failures_and_invalid_host_adapters_are_not_absence(self):
        def failing(_):
            raise RuntimeError('storage failure')
        with self.assertRaisesRegex(RuntimeError, 'storage failure'):
            auditum_view('ak_missing', **{**self.options, 'read_record': failing})
        for updates in [dict(can_read=lambda _: 1), dict(can_read=lambda _: None), dict(supported_contracts=[]),
                        dict(read_record=lambda _: self.f['record']), dict(read_receipt=lambda _: self.f['receipt'])]:
            with self.subTest(updates=updates), self.assertRaises((TypeError, ValueError)):
                auditum_view('ak_missing', **{**self.options, **updates})

    def test_receipt_negative_flags_timestamps_and_identity(self):
        for mutation in [dict(record_deleted=False), dict(audio_deleted=1), dict(contract='other'), dict(akousma_id='other'),
                         dict(audio_deletion_requested=False), dict(shared_audio_preserved=True), dict(created_at='2026-02-30T12:00:00Z')]:
            with self.subTest(mutation=mutation), self.assertRaises(ValueError):
                forgetting_receipt_view({**self.f['receipt'], **mutation}, 'ak_forgotten')

    def test_real_forgetting_reopen_and_reference_reindex(self):
        with TemporaryDirectory() as path:
            store = akousma.AkousmataStore(path)
            try:
                parent = akousma.new_akousma(audio={'asset_id': 'synthetic'}, originating_app='earworm')
                child = deepcopy(self.f['record'])
                child['lineage'] = dict(parent_akousma_ids=[parent['akousma_id']], relations=[akousma.relation('response_to', parent['akousma_id'])])
                store.put(parent)
                store.put(child)
                store.forget_with_receipt(parent['akousma_id'], actor='sensitive actor', reason='sensitive reason')
                view = store.auditum_view(child['akousma_id'], can_read=lambda _: True, supported_contracts=SUPPORTED)
                self.assertEqual(len(view['references']), 1)
                self.assertEqual(view['references'][0]['state'], 'forgotten')
                self.assertNotIn('sensitive', json.dumps(view))
                store.reindex()
                self.assertEqual(store.get(child['akousma_id']), child)
                self.assertEqual(store.auditum_view(child['akousma_id'], can_read=lambda _: True, supported_contracts=SUPPORTED), view)
                self.assertFalse(store.verify()['invalid_forgetting_receipts'])
            finally:
                store.close()
            reopened = akousma.AkousmataStore(path)
            try:
                self.assertEqual(reopened.auditum_view(child['akousma_id'], can_read=lambda _: True, supported_contracts=SUPPORTED), view)
                self.assertEqual(reopened.auditum_view(parent['akousma_id'], can_read=lambda _: False, supported_contracts=SUPPORTED)['state'], 'withheld')
            finally:
                reopened.close()

    def test_shared_audio_receipt_keeps_outcomes_distinct(self):
        with TemporaryDirectory() as path:
            store = akousma.AkousmataStore(path)
            try:
                import hashlib
                data = b'synthetic test bytes'
                uri = store.put_audio(data, ext='wav')
                audio = dict(asset_id='synthetic', uri=uri, content_hash='sha256:' + hashlib.sha256(data).hexdigest())
                first = akousma.new_akousma(audio=audio, originating_app='earworm')
                second = akousma.new_akousma(audio=audio, originating_app='earworm')
                store.put(first); store.put(second)
                store.forget_with_receipt(first['akousma_id'], delete_audio=True)
                receipt = store.auditum_view(first['akousma_id'], can_read=lambda _: True, supported_contracts=SUPPORTED)['receipt']
                self.assertTrue(receipt['shared_audio_preserved'])
                self.assertFalse(receipt['audio_deleted'])
                store.forget_with_receipt(second['akousma_id'], delete_audio=True)
                receipt = store.auditum_view(second['akousma_id'], can_read=lambda _: True, supported_contracts=SUPPORTED)['receipt']
                self.assertTrue(receipt['audio_deleted'])
                self.assertFalse(receipt['shared_audio_preserved'])
                self.assertFalse(store.resolve_uri(uri).exists())
            finally:
                store.close()

    def test_canonical_schema_rejects_receipt_content(self):
        from jsonschema import Draft7Validator
        canonical = ROOT / 'packages/core/schemas/auditum-view.schema.json'
        self.assertEqual(canonical.read_bytes(), (Path(akousma.__file__).parent / 'auditum-view.schema.json').read_bytes())
        validator = Draft7Validator(json.loads(canonical.read_text()))
        for identifier in [self.f['record']['akousma_id'], 'ak_missing', 'ak_forgotten', 'ak_withheld']:
            self.assertEqual(list(validator.iter_errors(auditum_view(identifier, **self.options))), [])
        leaked = deepcopy(self.f['expected']); leaked['references'][1]['receipt']['reason'] = 'private content'
        self.assertTrue(list(validator.iter_errors(leaked)))

    def test_unreleased_extension_names_remain_opaque_in_legacy_records(self):
        legacy = deepcopy(self.f['record']); legacy['extensions']['earworm_generation_decision'] = 'opaque legacy data'
        options = {**self.options, 'read_record': lambda i: legacy if i == legacy['akousma_id'] else self.options['read_record'](i)}
        self.assertEqual(auditum_view(legacy['akousma_id'], **options), self.f['expected'])
