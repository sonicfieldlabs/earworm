import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from jsonschema import Draft7Validator
import akousma
from akousma.record_evolution import next_record_errors, next_record_reference_errors, promote_legacy_appeal
ROOT = Path(__file__).resolve().parents[3]
FIXTURES = ROOT / "tests/contracts/evolution"


def read(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


class RecordEvolutionTest(unittest.TestCase):
    def test_appeal_parity_and_explicit_negotiation(self):
        fixture = read("appeal")
        before = deepcopy(fixture)
        result = promote_legacy_appeal(fixture["record"], fixture["options"])
        self.assertEqual(result, fixture["expected"])
        self.assertEqual(result["auditum"]["appeal"]["status"], "unreviewed")
        result["auditum"]["appeal"]["legacy_source"]["payload"]["unexpected"].append("changed")
        self.assertEqual(fixture, before)
        for options in ({**fixture["options"], "akousma_id": fixture["record"]["akousma_id"]},
                        {**fixture["options"], "supported_contracts": []}):
            with self.assertRaises(ValueError):
                promote_legacy_appeal(fixture["record"], options)

    def test_old_and_new_validation(self):
        legacy = Draft7Validator(akousma.load_schema())
        self.assertTrue(legacy.is_valid(read("appeal")["record"]))
        for record in [read("appeal")["expected"], read("research"), read("decision"), read("report")]:
            self.assertFalse(legacy.is_valid(record))
            self.assertEqual(akousma.validation_errors(record), [])
            self.assertEqual(json.loads(json.dumps(record)), record)

    def test_shared_mutation_cases(self):
        for case in read("cases"):
            with self.subTest(case=case["name"]):
                record = read(case["base"])
                target = record
                for key in case["path"][:-1]:
                    target = target[key]
                target[case["path"][-1]] = case["value"]
                self.assertEqual(not next_record_errors(record), case["valid"])

    def test_scope_and_chronology(self):
        for name in ("research", "decision", "report"):
            self.assertEqual(next_record_reference_errors(read(name), read("scope")), [])
        self.assertTrue(next_record_reference_errors(read("decision"), []))
        scope = read("scope")
        scope[2]["auditum"]["listenings"][0]["created_at"] = "2026-09-06T09:00:00Z"
        self.assertTrue(next_record_reference_errors(read("decision"), scope))
        self.assertTrue(next_record_reference_errors(read("decision"), read("scope") + [read("scope")[0]]))

    def test_store_revision_metadata_and_reindex(self):
        with tempfile.TemporaryDirectory() as directory:
            store = akousma.AkousmataStore(directory)
            try:
                source = read("appeal")["record"]
                store.put(source)
                revised = read("appeal")["expected"]
                store.put(revised)
                self.assertEqual(store.get(source["akousma_id"]), source)
                changed = deepcopy(revised)
                changed["auditum"]["appeal"]["status"] = "open"
                with self.assertRaises(ValueError):
                    store.put(changed)
                research = read("research")
                second = deepcopy(research["lineage"]["relations"][1])
                second["relation_id"] = "rel:alternative"
                second["criterion"]["criterion_id"] = "criterion:alternative"
                research["lineage"]["relations"].append(second)
                store.put(research)
                self.assertEqual(store.relation_details(research["akousma_id"]), research["lineage"]["relations"])
                self.assertEqual(len(store.relations(research["akousma_id"])), 2)
                store.reindex()
                self.assertEqual(store.get(research["akousma_id"]), research)
                self.assertEqual(len(store.relation_details(research["akousma_id"])), 3)
                changed = deepcopy(research)
                changed["lineage"]["relations"][1]["criterion"]["unit"] = "kHz"
                with self.assertRaises(ValueError):
                    store.put(changed)
                changed = deepcopy(research)
                changed["extensions"]["earworm_research"]["question"] = "Replacement question"
                with self.assertRaises(ValueError):
                    store.put(changed)
                store.put(read("decision"))
                self.assertEqual(store.get("ak_decision"), read("decision"))
            finally:
                store.close()

    def test_schema_copy(self):
        self.assertEqual((ROOT / "packages/core/schemas/akousma-1.7.schema.json").read_bytes(),
                         (ROOT / "packages/py-akousma/akousma/akousma-1.7.schema.json").read_bytes())

    def test_appeal_source_resolution_and_calendar(self):
        appeal = read("appeal")
        self.assertEqual(next_record_reference_errors(appeal["expected"], [appeal["record"]]), [])
        forged = deepcopy(appeal["expected"])
        forged["auditum"]["appeal"]["legacy_source"]["payload"]["unexpected"][1] = False
        self.assertTrue(next_record_reference_errors(forged, [appeal["record"]]))
        resolved = deepcopy(appeal["expected"])
        resolved["auditum"]["appeal"]["status"] = "resolved"
        self.assertTrue(next_record_errors(resolved))
        with self.assertRaises(ValueError):
            promote_legacy_appeal(appeal["record"], {**appeal["options"], "created_at": "2020-01-01T00:00:00Z"})
        self.assertTrue(next_record_reference_errors(read("decision"), [{"akousma_id": "ak_generation"}]))

    def test_outcome_and_stop_combinations(self):
        for outcome in ("keep", "discard", "revise", "variation"):
            proposal = read("decision")
            payload = proposal["extensions"]["earworm_generation_decision"]
            payload["outcome"] = outcome
            if outcome in ("keep", "discard"):
                payload["next_job"] = {"status": "none", "reason": "No next job proposed."}
                payload["stop_outcome"] = "stop"
            self.assertEqual(next_record_errors(proposal), [])

    def test_legacy_appeal_evidence_is_protected(self):
        source = read("appeal")["record"]
        with tempfile.TemporaryDirectory() as directory:
            store = akousma.AkousmataStore(directory)
            try:
                store.put(source)
                changed = deepcopy(source)
                changed["extensions"]["oida"]["appeal"]["status"] = "replacement"
                with self.assertRaises(ValueError):
                    store.put(changed)
                changed = deepcopy(source)
                changed["extensions"]["oida"]["other_field"] = "Ordinary curatorial metadata."
                store.put(changed)
                self.assertEqual(store.get(source["akousma_id"]), changed)
            finally:
                store.close()
