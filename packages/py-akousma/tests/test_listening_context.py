import json
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
import akousma
from akousma.listening_context import listening_context_errors, claim_validity_at, claim_retention_at

ROOT = Path(__file__).resolve().parents[3]


class ListeningContextTest(unittest.TestCase):
    def setUp(self):
        self.record = json.loads((ROOT / "tests/fixtures/human-context.akousma.json").read_text())
        self.context = self.record["extensions"]["earworm_listening_context"]

    def test_shared_cases_and_canonical_shape(self):
        self.assertEqual(akousma.validation_errors(self.record), [])
        self.assertEqual(listening_context_errors(self.context, self.record), [])
        for case in json.loads((ROOT / "tests/contracts/context-cases.json").read_text()):
            with self.subTest(case=case["name"]):
                changed = deepcopy(self.context)
                target = changed
                for key in case["path"][:-1]:
                    target = target[key]
                target[case["path"][-1]] = case["value"]
                self.assertEqual(not listening_context_errors(changed, self.record), case["valid"])

    def test_expiry_boundaries_and_independent_retention(self):
        before = deepcopy(self.record)
        claim = self.context["claims"][0]
        for time, status in (("2026-09-06T11:59:59.999Z", "not_yet_valid"), ("2026-09-06T12:00:00Z", "current"),
                             ("2026-09-06T12:59:59.999Z", "current"), ("2026-09-06T13:00:00Z", "expired")):
            self.assertEqual(claim_validity_at(claim, time), status)
        self.assertEqual(claim_retention_at(claim, "2026-09-06T13:00:00Z"), "review_not_due")
        self.assertEqual(claim_retention_at(claim, "2026-09-08T13:00:00Z"), "review_due")
        for time in ("2026-02-30T00:00:00Z", "0000-01-01T00:00:00Z"):
            with self.assertRaises(ValueError):
                claim_validity_at(claim, time)
        self.assertEqual(self.record, before)

    def test_qualified_unknowns(self):
        claim = deepcopy(self.context["claims"][0])
        claim["validity"] = {"status": "unknown", "reason": "Not assessed."}
        claim["retention"] = {"status": "unknown", "reason": "Needs policy."}
        self.assertEqual(claim_validity_at(claim, "2026-09-06T13:00:00Z"), "unknown")
        self.assertEqual(claim_retention_at(claim, "2026-09-06T13:00:00Z"), "policy_required")

    def test_store_protection_and_existing_forgetting_path(self):
        with tempfile.TemporaryDirectory() as directory:
            store = akousma.AkousmataStore(directory)
            try:
                store.put(self.record)
                changed = deepcopy(self.record)
                changed["extensions"]["earworm_listening_context"]["claims"][0]["retention"] = {"status": "unknown", "reason": "Changed."}
                with self.assertRaises(ValueError):
                    store.put(changed)
                changed = deepcopy(self.record)
                del changed["extensions"]["earworm_listening_context"]
                with self.assertRaises(ValueError):
                    store.put(changed)
                self.assertEqual(store.get(self.record["akousma_id"]), self.record)
                store.reindex()
                self.assertEqual(store.get(self.record["akousma_id"]), self.record)
                store.forget(self.record["akousma_id"], actor="fixture", reason="Explicit fixture retention decision.")
                self.assertIsNone(store.get(self.record["akousma_id"]))
                receipt = store.forgotten(self.record["akousma_id"])
                self.assertIsNotNone(receipt)
                self.assertNotIn("claim:context", json.dumps(receipt))
                with self.assertRaises(ValueError):
                    store.put(self.record)
            finally:
                store.close()

    def test_invalid_context_rejected_before_storage(self):
        self.context["contexts"][0]["report"]["human_rendering"] = {"status": "available", "rendering_refs": ["missing"]}
        with tempfile.TemporaryDirectory() as directory:
            store = akousma.AkousmataStore(directory)
            try:
                with self.assertRaises(ValueError):
                    store.put(self.record)
                self.assertIsNone(store.get(self.record["akousma_id"]))
            finally:
                store.close()

    def test_malformed_record_is_a_validation_error(self):
        self.record["auditum"]["listenings"] = [None]
        self.assertTrue(listening_context_errors(self.context, self.record))

    def test_schema_copy(self):
        self.assertEqual((ROOT / "packages/core/schemas/listening-context.schema.json").read_bytes(),
                         (ROOT / "packages/py-akousma/akousma/listening-context.schema.json").read_bytes())

    def test_separate_interpretation_rendering(self):
        cases = json.loads((ROOT / "tests/contracts/context-cases.json").read_text())
        rendering = next(case["value"] for case in cases if case["name"] == "interpretation has its own author and output")
        self.context["contexts"][0]["renderings"] = rendering
        self.context["contexts"][0]["report"]["human_rendering"] = {"status": "available", "rendering_refs": ["rendering:text"]}
        self.assertEqual(listening_context_errors(self.context, self.record), [])
        claim = self.context["claims"][0]
        claim["validity"] = {"status": "no_expiry", "issued_at": "2026-09-06T12:00:00Z", "reason": "Declared policy."}
        self.assertEqual(claim_validity_at(claim, "2026-09-09T12:00:00Z"), "current")

    def test_plural_accounts_resolve_their_own_apparatus(self):
        listener = deepcopy(self.record["auditum"]["listenings"][0])
        listener.update(listening_id="listening:second", listener_id="agent:second", listener_type="agent")
        self.record["auditum"]["listenings"].append(listener)
        access = deepcopy(self.record["extensions"]["earworm_listening_access"])
        access.update(declaration_id="access:second", subject_ref="record:another-subject")
        self.context["access_declarations"] = [access]
        context = deepcopy(self.context["contexts"][0])
        context.update(listening_ref=listener["listening_id"], subject_ref=access["subject_ref"], access_declaration_ref=access["declaration_id"])
        self.context["contexts"].append(context)
        self.assertEqual(listening_context_errors(self.context, self.record), [])
        self.context["access_declarations"].append(access)
        self.assertTrue(listening_context_errors(self.context, self.record))
