import tempfile
import unittest
from pathlib import Path

import akousma


class TestAkousmaRecord(unittest.TestCase):
    def test_schema_loads(self):
        schema = akousma.load_schema()
        self.assertEqual(schema["title"], "Akousma")

    def test_new_akousma_is_valid(self):
        rec = akousma.new_akousma(
            audio={"asset_id": "a1", "duration_seconds": 3.2},
            originating_app="oida",
            source_type="recorded",
            origin="live-input",
            listening={"oida.signal": {"class": "music-like"}},
        )
        self.assertEqual(akousma.validation_errors(rec), [])
        self.assertTrue(rec["akousma_id"].startswith("akm_"))
        self.assertEqual(rec["schema_version"], akousma.SCHEMA_VERSION)

    def test_invalid_is_detected(self):
        bad = {"akousma_id": "x", "schema_version": "1.0.0", "created_at": "now"}  # missing audio/provenance/lineage
        self.assertTrue(akousma.validation_errors(bad))

    def test_bad_enum_is_detected(self):
        rec = akousma.new_akousma(audio={"asset_id": "a1"}, originating_app="oida", source_type="bogus")
        self.assertTrue(akousma.validation_errors(rec))

    def test_ids_are_sortable_and_unique(self):
        ids = [akousma.new_id() for _ in range(50)]
        self.assertEqual(len(set(ids)), 50)


class TestAkousmataStore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.store = akousma.AkousmataStore(self.tmp.name)

    def tearDown(self):
        self.store.close()
        self.tmp.cleanup()

    def test_content_addressed_audio(self):
        uri = self.store.put_audio(b"RIFFfake-wav-bytes", ext="wav")
        self.assertTrue(uri.startswith("akousmata://objects/"))
        path = self.store.resolve_uri(uri)
        self.assertTrue(path.exists())
        # same bytes -> same uri (dedup)
        self.assertEqual(uri, self.store.put_audio(b"RIFFfake-wav-bytes", ext="wav"))

    def test_roundtrip_query_and_lineage(self):
        parent = akousma.new_akousma(
            audio={"asset_id": "a1"}, originating_app="oida", source_type="recorded", origin="file"
        )
        self.store.put(parent)
        child = akousma.new_akousma(
            audio={"asset_id": "a2"}, originating_app="germ", source_type="generated", origin="generated",
            parent_akousma_ids=[parent["akousma_id"]], operation="transform", prompt="metallic",
        )
        self.store.put(child)

        self.assertEqual(self.store.get(parent["akousma_id"])["akousma_id"], parent["akousma_id"])
        self.assertEqual(self.store.parents(child["akousma_id"]), [parent["akousma_id"]])
        self.assertEqual(self.store.children(parent["akousma_id"]), [child["akousma_id"]])
        self.assertEqual(self.store.ancestors(child["akousma_id"]), [parent["akousma_id"]])
        self.assertEqual([r["akousma_id"] for r in self.store.query(originating_app="oida")], [parent["akousma_id"]])
        self.assertEqual([r["akousma_id"] for r in self.store.query(originating_app="germ")], [child["akousma_id"]])

    def test_put_rejects_invalid(self):
        with self.assertRaises(ValueError):
            self.store.put({"akousma_id": "x"})


if __name__ == "__main__":
    unittest.main()
