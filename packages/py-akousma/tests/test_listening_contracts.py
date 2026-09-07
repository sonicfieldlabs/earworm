import json
import unittest
import tempfile
from copy import deepcopy
from pathlib import Path

import akousma
from akousma.listening_contracts import (
    LISTENING_ACCESS_CONTRACT, listening_access_errors,
    assert_supported_contracts, adapt_listening_passes,
)

ROOT = Path(__file__).resolve().parents[3]
CASES = ROOT / "tests/contracts"


class ListeningContractsTest(unittest.TestCase):
    def test_shared_access_cases(self):
        for case in json.loads((CASES / "access-cases.json").read_text()):
            with self.subTest(case=case["name"]):
                self.assertEqual(not listening_access_errors(case["value"]), case["valid"])

    def test_shared_adapter_and_source_preservation(self):
        fixture = json.loads((CASES / "pass-adapter.json").read_text())
        before = deepcopy(fixture["input"])
        result = adapt_listening_passes(**fixture["input"])
        self.assertEqual(result, fixture["expected"])
        result["source"]["passes"][0]["route"].append("changed")
        result["listenings"][0]["route"].append("changed")
        self.assertEqual(fixture["input"], before)
        for kind in ("human", "agent", "hybrid", "community", "institution", "sensor", "habitat", "other_animal", "ensemble", "other"):
            fixture["input"]["participants"][0]["type"] = kind
            self.assertEqual(adapt_listening_passes(**fixture["input"])["listenings"][0]["listener_type"], kind)

    def test_shared_invalid_adapters(self):
        for case in json.loads((CASES / "invalid-adapters.json").read_text()):
            with self.subTest(case=case["name"]), self.assertRaises((ValueError, TypeError)):
                adapt_listening_passes(**case["input"])

    def test_opaque_roundtrip_is_not_contract_support(self):
        access = json.loads((ROOT / "packages/core/fixtures/synthetic-wideband.listening-access.json").read_text())
        record = akousma.new_akousma(audio={"asset_id": "asset:synthetic-01"}, originating_app="fixture",
                                   extensions={"earworm_listening_access": access, "opaque_future": {"unknown": ["preserve", 0, None]}})
        self.assertEqual(akousma.validation_errors(record), [])
        restored = json.loads(json.dumps(record))
        self.assertEqual(restored, record)
        self.assertEqual(listening_access_errors(restored["extensions"]["earworm_listening_access"]), [])
        assert_supported_contracts([LISTENING_ACCESS_CONTRACT], [LISTENING_ACCESS_CONTRACT])
        with self.assertRaises(ValueError):
            assert_supported_contracts([LISTENING_ACCESS_CONTRACT], [])
        with self.assertRaises(TypeError):
            assert_supported_contracts("contract", [])

    def test_bundled_schema_matches_canonical(self):
        self.assertEqual((ROOT / "packages/core/schemas/listening-access.schema.json").read_bytes(),
                         (ROOT / "packages/py-akousma/akousma/listening-access.schema.json").read_bytes())

    def test_nonfinite_rate(self):
        access = json.loads((ROOT / "packages/core/fixtures/synthetic-wideband.listening-access.json").read_text())
        for number in (float("nan"), float("inf")):
            access["model_input"]["sample_rate_hz"] = number
            self.assertTrue(listening_access_errors(access))

    def test_store_preserves_contract_evidence(self):
        access = json.loads((ROOT / "packages/core/fixtures/synthetic-wideband.listening-access.json").read_text())
        adapted = json.loads((CASES / "pass-adapter.json").read_text())["expected"]
        record = akousma.new_akousma(audio={"asset_id": "asset:synthetic-01"}, originating_app="fixture",
            extensions={"earworm_listening_access": access, "akouo_pass_adapter": adapted})
        with tempfile.TemporaryDirectory() as directory:
            store = akousma.AkousmataStore(directory)
            try:
                store.put(record)
                self.assertEqual(store.get(record["akousma_id"]), record)
                for key in ("earworm_listening_access", "akouo_pass_adapter"):
                    changed = deepcopy(record)
                    del changed["extensions"][key]
                    with self.assertRaises(ValueError):
                        store.put(changed)
                    self.assertEqual(store.get(record["akousma_id"]), record)
                changed = deepcopy(record)
                changed["extensions"]["ordinary_curatorial_note"] = "Editable metadata."
                store.put(changed)
                self.assertEqual(store.get(record["akousma_id"]), changed)
                malformed = deepcopy(record)
                malformed["akousma_id"] = "ak_invalid_fixture"
                malformed["extensions"]["earworm_listening_access"]["model_input"]["sample_rate_hz"] = 8000
                with self.assertRaises(ValueError):
                    store.put(malformed)
            finally:
                store.close()
