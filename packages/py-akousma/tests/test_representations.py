"""Shared synthetic cases exercise the installed Python representation contract."""
from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest
from akousma import validation_errors, AkousmataStore
from akousma.representations import (
    REPRESENTATION_CONTRACTS, admit_representation_record, representation_errors,
    representation_record_errors, record_19_errors,
)

ROOT = Path(__file__).resolve().parents[3] / "tests/contracts/representations"


def read(name):
    return json.loads((ROOT / (name + ".json")).read_text())


@pytest.mark.parametrize("entry", read("cases"), ids=lambda item: item["name"])
def test_shared_representation_cases(entry):
    value = read(entry["base"])
    if entry["action"] != "none":
        parent = value
        for key in entry["path"][:-1]:
            parent = parent[key]
        key = entry["path"][-1]
        if entry["action"] == "delete":
            del parent[key]
        elif entry["action"] == "append":
            parent[key].append(entry["value"])
        else:
            parent[key] = entry["value"]
    assert (not representation_record_errors(value)) == entry["valid"]


@pytest.mark.parametrize("name", ["listen", "account", "sound", "work", "partial", "read-file", "no-response", "refused"])
def test_admission_retains_complete_text_and_does_not_mutate(name):
    value = read(name)
    before = deepcopy(value)
    result = admit_representation_record(value, supported_contracts=REPRESENTATION_CONTRACTS)
    assert result == value
    result["representations"][0]["subject_ref"] = "changed"
    assert value == before


def test_external_artifacts_require_exact_bytes_from_host():
    value = read("work")
    content = {r["representation_id"]: r["artifact"].pop("inline_text").encode("utf-8") for r in value["representations"]}
    with pytest.raises(ValueError, match="unavailable"):
        admit_representation_record(value, supported_contracts=REPRESENTATION_CONTRACTS)
    assert admit_representation_record(value, supported_contracts=REPRESENTATION_CONTRACTS,
                                       resolve_artifact=lambda r: content[r["representation_id"]]) == value
    with pytest.raises(ValueError, match="mismatched"):
        admit_representation_record(value, supported_contracts=REPRESENTATION_CONTRACTS, resolve_artifact=lambda r: b"wrong")


def test_instruction_is_not_self_adopting():
    with pytest.raises(ValueError, match="Unsupported"):
        admit_representation_record(read("listen"), supported_contracts=[])
    value = read("instruction")
    with pytest.raises(ValueError, match="owner"):
        admit_representation_record(value, supported_contracts=REPRESENTATION_CONTRACTS)
    assert admit_representation_record(value, supported_contracts=REPRESENTATION_CONTRACTS, validate_binding=lambda b, a: []) == value
    with pytest.raises(ValueError, match="Revoked"):
        admit_representation_record(value, supported_contracts=REPRESENTATION_CONTRACTS, validate_binding=lambda b, a: ["Revoked by owner"])


@pytest.mark.parametrize("name", ["return", "original-return"])
def test_return_must_resolve_against_previous_owner_operation(name):
    value = read(name)
    with pytest.raises(ValueError, match="unresolved"):
        admit_representation_record(value, supported_contracts=REPRESENTATION_CONTRACTS)
    assert admit_representation_record(value, supported_contracts=REPRESENTATION_CONTRACTS, resolve_operation=lambda ref: read("previous-operation")) == value
    if name == "return":
        with pytest.raises(ValueError, match="previous output"):
            admit_representation_record(value, supported_contracts=REPRESENTATION_CONTRACTS,
                                       resolve_operation=lambda ref: {**read("previous-operation"), "output_representation_refs": []})


def test_record_version_dispatch_and_store_admission(tmp_path):
    value = read("record-19")
    assert not record_19_errors(value)
    assert not validation_errors(value)
    wrong = deepcopy(value)
    wrong["extensions"]["earworm_representation"]["record_ref"] = "other"
    assert record_19_errors(wrong)
    placeholder = deepcopy(value)
    placeholder["audio"] = {"asset_id": "placeholder"}
    assert record_19_errors(placeholder)
    with pytest.raises(ValueError, match="store adapter"):
        AkousmataStore(tmp_path).put(value)


def test_prior_account_derivative_cannot_hide_in_independent_context():
    value = read("return")
    earlier = read("account")["representations"][1]
    excerpt = deepcopy(earlier)
    excerpt["representation_id"] = "fixture:context-excerpt"
    raw = earlier["artifact"]["inline_text"][:6].encode("utf-8")
    excerpt["artifact"].update(inline_text=raw.decode("utf-8"), ref="fixture:context-excerpt",
                              sha256=sha256(raw).hexdigest(), byte_count=len(raw))
    excerpt["origin"] = {"kind": "transformed", "domain": "non_acoustic", "source_refs": [earlier["representation_id"]]}
    excerpt["preservation"] = {"layout": "transformed", "losses": ["Remaining account omitted."]}
    value["representations"].extend([earlier, excerpt])
    value["relations"].append({"relation_id": "fixture:context-transform", "kind": "transformed_from", "from_ref": excerpt["representation_id"],
                               "to_ref": earlier["representation_id"], "declared_by": "fixture-author", "method_ref": "fixture/selection/v1", "losses": excerpt["preservation"]["losses"]})
    value["accesses"].append({"contract": "earworm/representation-access/v1", "access_id": "fixture:context-access", "operation_ref": value["operation_ref"],
                              "representation_ref": earlier["representation_id"], "received_representation_ref": excerpt["representation_id"], "role": "context", "status": "available",
                              "coverage": {"kind": "partial", "unit": "byte", "ranges": [{"start": 0, "end": excerpt["artifact"]["byte_count"]}], "omissions": ["Remaining account omitted."]}})
    assert not representation_record_errors(value)
    with pytest.raises(ValueError, match="prior account"):
        admit_representation_record(value, supported_contracts=REPRESENTATION_CONTRACTS, resolve_operation=lambda ref: read("previous-operation"))


def test_nonfinite_unknown_and_audio_origin():
    value = read("listen")
    value["representations"][0]["artifact"]["byte_count"] = float("nan")
    assert representation_record_errors(value)
    assert representation_errors(None)
    audio = read("listen")["representations"][0]
    del audio["artifact"]["inline_text"]
    del audio["encoding"]
    audio.update(form="audio", media_type="audio/wav", origin={"kind": "generated", "domain": "non_acoustic", "source_refs": []},
                 preservation={"layout": "not_applicable", "losses": []})
    assert not representation_errors(audio)
