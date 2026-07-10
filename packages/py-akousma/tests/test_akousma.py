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

    def test_relations_roundtrip(self):
        first = akousma.new_akousma(
            audio={"asset_id": "a1"}, originating_app="oida", summary="harbor, first take"
        )
        self.store.put(first)
        second = akousma.new_akousma(
            audio={"asset_id": "a2"},
            originating_app="oida",
            summary="harbor, second take",
            relations=[akousma.relation("series_with", first["akousma_id"], note="same position, one year later")],
        )
        self.assertEqual(akousma.validation_errors(second), [])
        self.store.put(second)

        self.assertEqual(
            self.store.relations(second["akousma_id"]),
            [{"type": "series_with", "target_akousma_id": first["akousma_id"]}],
        )
        incoming = self.store.related(first["akousma_id"])
        self.assertEqual(incoming, [{"type": "series_with", "akousma_id": second["akousma_id"], "direction": "incoming"}])
        self.assertEqual(self.store.related(first["akousma_id"], rel_type="variant_of"), [])
        # relations are kinship, not parenthood
        self.assertEqual(self.store.parents(second["akousma_id"]), [])

    def test_relation_helper_rejects_unknown_type(self):
        with self.assertRaises(ValueError):
            akousma.relation("cousin_of", "akm_x")

    def test_add_listening_envelope(self):
        rec = akousma.new_akousma(audio={"asset_id": "a1"}, originating_app="oida")
        akousma.add_listening(
            rec, "akouo.memory-lineage-listening", {"main_reading": "recurrence"},
            contract="akouo/v0.6", summary="third in series",
        )
        entry = rec["listening"]["akouo.memory-lineage-listening"]
        self.assertEqual(entry["contract"], "akouo/v0.6")
        self.assertEqual(entry["payload"], {"main_reading": "recurrence"})
        self.assertEqual(akousma.validation_errors(rec), [])

    def test_query_filters(self):
        a = akousma.new_akousma(
            audio={"asset_id": "a1", "content_hash": "sha256:aaa"},
            originating_app="oida", tags=["harbor"], summary="water and machinery",
        )
        b = akousma.new_akousma(
            audio={"asset_id": "a2", "content_hash": "sha256:bbb"},
            originating_app="germ", tags=["voice"],
        )
        self.store.put(a)
        self.store.put(b)
        self.assertEqual([r["akousma_id"] for r in self.store.query(tag="harbor")], [a["akousma_id"]])
        self.assertEqual([r["akousma_id"] for r in self.store.find_by_hash("sha256:bbb")], [b["akousma_id"]])
        self.assertEqual([r["akousma_id"] for r in self.store.query(text="machinery")], [a["akousma_id"]])
        self.assertEqual(len(self.store.query(since="2020-01-01T00:00:00Z")), 2)
        self.assertEqual(self.store.query(until="2020-01-01T00:00:00Z"), [])

    def test_descendants_walk(self):
        a = akousma.new_akousma(audio={"asset_id": "a"}, originating_app="oida")
        self.store.put(a)
        b = akousma.new_akousma(
            audio={"asset_id": "b"}, originating_app="germ", parent_akousma_ids=[a["akousma_id"]]
        )
        self.store.put(b)
        c = akousma.new_akousma(
            audio={"asset_id": "c"}, originating_app="germ", parent_akousma_ids=[b["akousma_id"]]
        )
        self.store.put(c)
        self.assertEqual(set(self.store.descendants(a["akousma_id"])), {b["akousma_id"], c["akousma_id"]})

    def test_verify_reports_absences(self):
        rec = akousma.new_akousma(
            audio={"asset_id": "a1", "uri": "akousmata://objects/deadbeef.wav"},
            originating_app="oida",
            parent_akousma_ids=["akm_MISSINGPARENT"],
            relations=[akousma.relation("recurrence_of", "akm_MISSINGTARGET")],
        )
        self.store.put(rec)
        report = self.store.verify()
        self.assertTrue(report["dangling_parents"])
        self.assertTrue(report["dangling_relations"])
        self.assertTrue(report["missing_audio"])
        self.assertEqual(report["invalid_records"], [])

    def test_reindex_rebuilds_edges(self):
        a = akousma.new_akousma(audio={"asset_id": "a"}, originating_app="oida")
        self.store.put(a)
        b = akousma.new_akousma(
            audio={"asset_id": "b"}, originating_app="germ",
            parent_akousma_ids=[a["akousma_id"]],
            relations=[akousma.relation("variant_of", a["akousma_id"])],
        )
        self.store.put(b)
        self.store.conn.execute("DELETE FROM lineage_edges")
        self.store.conn.execute("DELETE FROM relation_edges")
        self.store.conn.commit()
        count = self.store.reindex()
        self.assertEqual(count, 2)
        self.assertEqual(self.store.parents(b["akousma_id"]), [a["akousma_id"]])
        self.assertEqual(self.store.relations(b["akousma_id"]), [{"type": "variant_of", "target_akousma_id": a["akousma_id"]}])

    def test_v1_records_still_valid(self):
        rec = akousma.new_akousma(audio={"asset_id": "a1"}, originating_app="oida")
        rec["schema_version"] = "1.0.0"
        rec["lineage"].pop("relations", None)
        rec.pop("summary", None)
        self.assertEqual(akousma.validation_errors(rec), [])


if __name__ == "__main__":
    unittest.main()
