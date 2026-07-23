import tempfile
import unittest

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

    def test_location_and_capture_are_valid(self):
        rec = akousma.new_akousma(
            audio={"asset_id": "a1"},
            originating_app="oida",
            origin="live-input",
            location=akousma.location(6.2442, -75.5812, label="río Medellín", source="gps"),
            capture=akousma.capture("past", seconds=30, trigger="remote-ear"),
        )
        self.assertEqual(akousma.validation_errors(rec), [])
        self.assertEqual(rec["location"]["lat"], 6.2442)
        self.assertEqual(rec["capture"]["direction"], "past")
        self.assertIn("captured_at", rec["location"])
        self.assertIn("triggered_at", rec["capture"])

    def test_location_builder_validates(self):
        with self.assertRaises(ValueError):
            akousma.location(91.0, 0.0)
        with self.assertRaises(ValueError):
            akousma.location(0.0, 181.0)
        with self.assertRaises(ValueError):
            akousma.location(0.0, 0.0, source="astral")

    def test_capture_builder_validates(self):
        with self.assertRaises(ValueError):
            akousma.capture("sideways")
        with self.assertRaises(ValueError):
            akousma.capture("past", seconds=-1)

    def test_out_of_range_location_fails_schema(self):
        rec = akousma.new_akousma(audio={"asset_id": "a1"}, originating_app="oida")
        rec["location"] = {"lat": 123.0, "lon": 0.0}
        self.assertTrue(akousma.validation_errors(rec))

    def test_unknown_top_level_field_is_tolerated(self):
        rec = akousma.new_akousma(audio={"asset_id": "a1"}, originating_app="oida")
        rec["weather"] = "light rain"
        self.assertEqual(akousma.validation_errors(rec), [])

    def test_covenant_block_is_valid(self):
        rec = akousma.new_akousma(
            audio={"asset_id": "a1"},
            originating_app="oida",
            origin="live-input",
            covenant=akousma.covenant(
                "river-covenant/2",
                name="river covenant",
                contract="akouo/v0.7",
                extends=["algophonya/v7"],
                withheld=[{"rule": "do_not_reveal", "subject": "transcript", "count": 1}],
                commitments=1,
            ),
        )
        self.assertEqual(akousma.validation_errors(rec), [])
        self.assertEqual(rec["covenant"]["id"], "river-covenant/2")
        self.assertEqual(rec["covenant"]["withheld"][0]["subject"], "transcript")

    def test_covenant_builder_validates(self):
        with self.assertRaises(ValueError):
            akousma.covenant("")
        with self.assertRaises(ValueError):
            akousma.covenant("x", commitments=-1)

    def test_covenant_without_id_fails_schema(self):
        rec = akousma.new_akousma(audio={"asset_id": "a1"}, originating_app="oida")
        rec["covenant"] = {"name": "anonymous rules"}
        self.assertTrue(akousma.validation_errors(rec))

    def test_accountable_auditum_is_valid_and_plural(self):
        listenings = [
            {
                "listening_id": "lst_signal",
                "listener_id": "oida-signal",
                "listener_type": "agent",
                "created_at": "2026-07-22T12:00:00Z",
                "report_namespace": "oida.signal",
                "contract": "akouo/v0.8",
                "claim_set_ref": "#/listening/oida.signal/payload/listening_claims",
                "route": ["signal-inspection-listening"],
            },
            {
                "listening_id": "lst_context",
                "listener_id": "oida-context",
                "listener_type": "agent",
                "created_at": "2026-07-22T12:00:01Z",
                "report_namespace": "akouo.ecological-posthuman-listening",
                "contract": "akouo/v0.8",
                "route": ["ecological-posthuman-listening"],
            },
        ]
        block = akousma.auditum(
            listenings=listenings,
            disagreements=[{
                "id": "dis_1",
                "subject": "source identity",
                "listening_ids": ["lst_signal", "lst_context"],
                "positions": [
                    {"listening_id": "lst_signal", "statement": "Source remains undetermined", "claim_category": "undetermined"},
                    {"listening_id": "lst_context", "statement": "Water is a contextual possibility", "claim_category": "interpreted"},
                ],
                "status": "preserved",
            }],
            honest_absences=[{
                "id": "abs_1",
                "kind": "not_retained",
                "subject": "raw audio",
                "attributed_to": "local retention boundary",
                "count": 1,
            }],
            actions=[{
                "action_id": "act_1",
                "proposal": "Recommend a calibrated re-listening",
                "status": "proposed",
                "authority": {
                    "mode": "recommend",
                    "scopes": ["recommend_next_listening"],
                    "requires_confirmation": True,
                    "reversible": True,
                },
            }],
        )
        rec = akousma.new_akousma(
            audio={"asset_id": "a1"}, originating_app="oida", auditum=block
        )
        self.assertEqual(akousma.validation_errors(rec), [])
        self.assertEqual(rec["schema_version"], "1.4.0")
        self.assertEqual(len(rec["auditum"]["listenings"]), 2)
        self.assertEqual(rec["auditum"]["disagreements"][0]["status"], "preserved")

    def test_auditum_builder_rejects_false_plurality(self):
        listening = {
            "listening_id": "lst_1",
            "listener_id": "listener_1",
            "listener_type": "agent",
            "created_at": "2026-07-22T12:00:00Z",
            "report_namespace": "oida.signal",
            "contract": "akouo/v0.8",
        }
        with self.assertRaises(ValueError):
            akousma.auditum(listenings=[listening, listening])
        with self.assertRaises(ValueError):
            akousma.auditum(
                listenings=[listening],
                disagreements=[{
                    "id": "dis_1",
                    "subject": "identity",
                    "listening_ids": ["lst_1", "lst_missing"],
                    "positions": [
                        {"listening_id": "lst_1", "statement": "unknown"},
                        {"listening_id": "lst_missing", "statement": "known"},
                    ],
                    "status": "preserved",
                }],
            )

    def test_v1_1_records_still_valid(self):
        rec = akousma.new_akousma(
            audio={"asset_id": "a1"},
            originating_app="oida",
            location=akousma.location(6.0, -75.0),
            capture=akousma.capture("future", seconds=10),
        )
        rec["schema_version"] = "1.1.0"
        rec.pop("location", None)
        rec.pop("capture", None)
        self.assertEqual(akousma.validation_errors(rec), [])


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

    def test_query_tag_is_exact_membership(self):
        tagged = akousma.new_akousma(
            audio={"asset_id": "a1"}, originating_app="oida", tags=["harbor"],
        )
        lookalike = akousma.new_akousma(
            audio={"asset_id": "a2"}, originating_app="oida",
            tags=["harbor-night"],
            summary='mentions "harbor" in prose only',
        )
        lookalike["annotations"] = {"note": 'she said "harbor" twice'}
        self.store.put(tagged)
        self.store.put(lookalike)
        self.assertEqual(
            [r["akousma_id"] for r in self.store.query(tag="harbor")],
            [tagged["akousma_id"]],
        )
        self.assertEqual(self.store.query(tag="harb"), [])

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

    def test_tags_counts(self):
        for tags in (["harbor", "field"], ["harbor"], []):
            self.store.put(akousma.new_akousma(audio={"asset_id": f"a{len(tags)}"}, originating_app="oida", tags=tags))
        self.assertEqual(
            self.store.tags(),
            [{"tag": "harbor", "count": 2}, {"tag": "field", "count": 1}],
        )

    def test_changed_since(self):
        rec = akousma.new_akousma(audio={"asset_id": "a1"}, originating_app="oida")
        self.store.put(rec)
        self.assertEqual(self.store.changed_since("2000-01-01T00:00:00Z")[0]["akousma_id"], rec["akousma_id"])
        self.assertEqual(self.store.changed_since(rec["created_at"]), [])

    def test_changed_since_tie_safe_cursor(self):
        records = []
        for index in range(3):
            record = akousma.new_akousma(audio={"asset_id": f"tie-{index}"}, originating_app="oida")
            record["created_at"] = "2026-07-10T12:00:00Z"
            self.store.put(record)
            records.append(record)
        ordered_ids = sorted(record["akousma_id"] for record in records)
        found = self.store.changed_since("2026-07-10T12:00:00Z", after_id=ordered_ids[0])
        self.assertEqual([record["akousma_id"] for record in found], ordered_ids[1:])

    def test_forget(self):
        data = b"RIFF-forget-me"
        uri = self.store.put_audio(data, ext="wav")
        rec = akousma.new_akousma(
            audio={"asset_id": "a1", "uri": uri, "content_hash": "sha256:" + __import__("hashlib").sha256(data).hexdigest()},
            originating_app="oida",
        )
        self.store.put(rec)
        path = self.store.resolve_uri(uri)
        self.assertTrue(path.exists())
        self.assertTrue(self.store.forget(rec["akousma_id"], delete_audio=True))
        self.assertIsNone(self.store.get(rec["akousma_id"]))
        self.assertFalse(path.exists())
        self.assertFalse(self.store.forget("akm_missing"))

    def test_forget_keeps_shared_audio(self):
        data = b"RIFF-shared"
        uri = self.store.put_audio(data, ext="wav")
        digest = "sha256:" + __import__("hashlib").sha256(data).hexdigest()
        first = akousma.new_akousma(audio={"asset_id": "a1", "uri": uri, "content_hash": digest}, originating_app="oida")
        second = akousma.new_akousma(audio={"asset_id": "a2", "uri": uri, "content_hash": digest}, originating_app="germ")
        self.store.put(first)
        self.store.put(second)
        self.assertTrue(self.store.forget(first["akousma_id"], delete_audio=True))
        self.assertTrue(self.store.resolve_uri(uri).exists())

    def test_v1_records_still_valid(self):
        rec = akousma.new_akousma(audio={"asset_id": "a1"}, originating_app="oida")
        rec["schema_version"] = "1.0.0"
        rec["lineage"].pop("relations", None)
        rec.pop("summary", None)
        self.assertEqual(akousma.validation_errors(rec), [])

    def test_location_roundtrip_and_queries(self):
        here = akousma.new_akousma(
            audio={"asset_id": "a1"},
            originating_app="oida",
            location=akousma.location(6.2442, -75.5812, label="río Medellín", source="gps"),
            capture=akousma.capture("past", seconds=30),
        )
        far = akousma.new_akousma(
            audio={"asset_id": "a2"},
            originating_app="oida",
            location=akousma.location(52.52, 13.405, label="Berlin"),
        )
        unlocated = akousma.new_akousma(audio={"asset_id": "a3"}, originating_app="germ")
        for rec in (here, far, unlocated):
            self.store.put(rec)

        located_ids = {r["akousma_id"] for r in self.store.locations()}
        self.assertEqual(located_ids, {here["akousma_id"], far["akousma_id"]})
        self.assertEqual(
            [r["akousma_id"] for r in self.store.query(has_location=False)],
            [unlocated["akousma_id"]],
        )
        nearby = self.store.near(6.2450, -75.5800, radius_km=2.0)
        self.assertEqual([r["akousma_id"] for r in nearby], [here["akousma_id"]])
        self.assertEqual(self.store.near(0.0, 0.0, radius_km=5.0), [])
        fetched = self.store.get(here["akousma_id"])
        self.assertEqual(fetched["capture"]["direction"], "past")
        self.assertEqual(fetched["location"]["label"], "río Medellín")

    def test_unknown_fields_roundtrip_through_store(self):
        rec = akousma.new_akousma(audio={"asset_id": "a1"}, originating_app="oida")
        rec["weather"] = {"condition": "light rain"}
        self.store.put(rec)
        self.assertEqual(self.store.get(rec["akousma_id"])["weather"], {"condition": "light rain"})

    def test_covenant_query_and_reindex(self):
        under = akousma.new_akousma(
            audio={"asset_id": "a1"},
            originating_app="oida",
            covenant=akousma.covenant("river-covenant/2"),
        )
        free = akousma.new_akousma(audio={"asset_id": "a2"}, originating_app="oida")
        self.store.put(under)
        self.store.put(free)
        self.assertEqual(
            [r["akousma_id"] for r in self.store.query(covenant_id="river-covenant/2")],
            [under["akousma_id"]],
        )
        self.assertEqual(self.store.query(covenant_id="other-covenant"), [])
        self.store.conn.execute("UPDATE akousmata SET covenant_id=NULL")
        self.store.conn.commit()
        self.assertEqual(self.store.query(covenant_id="river-covenant/2"), [])
        self.store.reindex()
        self.assertEqual(
            [r["akousma_id"] for r in self.store.query(covenant_id="river-covenant/2")],
            [under["akousma_id"]],
        )

    def test_auditum_query_and_reindex(self):
        listenings = [
            {
                "listening_id": "lst_1",
                "listener_id": "oida",
                "listener_type": "agent",
                "created_at": "2026-07-22T12:00:00Z",
                "report_namespace": "oida.signal",
                "contract": "akouo/v0.8",
            },
            {
                "listening_id": "lst_2",
                "listener_id": "akouo",
                "listener_type": "agent",
                "created_at": "2026-07-22T12:00:01Z",
                "report_namespace": "akouo.acoulogical-object-listening",
                "contract": "akouo/v0.8",
            },
        ]
        accountable = akousma.new_akousma(
            audio={"asset_id": "a1"},
            originating_app="oida",
            auditum=akousma.auditum(
                listenings=listenings,
                disagreements=[{
                    "id": "dis_1",
                    "subject": "source",
                    "listening_ids": ["lst_1", "lst_2"],
                    "positions": [
                        {"listening_id": "lst_1", "statement": "undetermined"},
                        {"listening_id": "lst_2", "statement": "ambiguous object"},
                    ],
                    "status": "preserved",
                }],
            ),
        )
        legacy = akousma.new_akousma(audio={"asset_id": "a2"}, originating_app="oida")
        self.store.put(accountable)
        self.store.put(legacy)
        self.assertEqual(
            [record["akousma_id"] for record in self.store.query(has_auditum=True)],
            [accountable["akousma_id"]],
        )
        self.assertEqual(
            [record["akousma_id"] for record in self.store.query(has_disagreement=True)],
            [accountable["akousma_id"]],
        )
        self.store.conn.execute(
            "UPDATE akousmata SET auditum_contract=NULL, listening_count=0, disagreement_count=0, honest_absence_count=0"
        )
        self.store.conn.commit()
        self.assertEqual(self.store.query(has_auditum=True), [])
        self.store.reindex()
        self.assertEqual(
            [record["akousma_id"] for record in self.store.query(has_disagreement=True)],
            [accountable["akousma_id"]],
        )

    def test_reindex_rehoists_location(self):
        rec = akousma.new_akousma(
            audio={"asset_id": "a1"},
            originating_app="oida",
            location=akousma.location(6.2442, -75.5812),
        )
        self.store.put(rec)
        self.store.conn.execute("UPDATE akousmata SET lat=NULL, lon=NULL")
        self.store.conn.commit()
        self.assertEqual(self.store.locations(), [])
        self.store.reindex()
        self.assertEqual(
            [r["akousma_id"] for r in self.store.locations()], [rec["akousma_id"]]
        )


if __name__ == "__main__":
    unittest.main()
