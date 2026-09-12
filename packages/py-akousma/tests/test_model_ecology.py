from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest
from akousma.deployments import DeploymentRegistry
from akousma.model_ecology import embedding, contract_errors
from akousma.resource_admission import heavy_lease, admission_status


def space():
    return dict(
        model="test/encoder",
        revision="a" * 40,
        preprocessing_sha256="b" * 64,
        dimensions=3,
        pooling="mean",
        metric="cosine",
    )


def manifest():
    return dict(
        contract="earworm/model-deployment/v1",
        id="test-v1",
        owner="test",
        adapter="test",
        capabilities=["tag_events"],
        components=[dict(id="weights", revision="a" * 40, sha256="b" * 64)],
        runtime_revision="c" * 40,
        license_review="private-test-review",
        validation_receipt="private-test-receipt",
        enabled=True,
        provisioned=True,
        max_input_seconds=10,
        max_output_seconds=0,
        measured_peak_memory_mib=64,
    )


def test_embedding_space_and_legacy():
    vector = dict(space=space(), vector=[1, 0, 0])
    assert embedding(vector)
    assert embedding([1, 0, 0]) is None
    for bad in ([1, float("nan"), 0], [1, True, 0], [1, 0], [1, float("inf"), 0]):
        assert embedding(dict(space=space(), vector=bad)) is None
    other = deepcopy(vector)
    other["space"]["revision"] = "c" * 40
    assert embedding(vector)[0] != embedding(other)[0]


def test_deployment_gates_and_copy_isolation():
    registry = DeploymentRegistry("test")
    registry.register_adapter("test", ["tag_events"], verify=lambda manifest: [])
    for field, bad in [
        ("runtime_revision", "main"),
        ("provisioned", False),
        ("measured_peak_memory_mib", None),
        ("license_review", "pending"),
        ("capabilities", ["shell"]),
        ("adapter", "missing"),
    ]:
        value = manifest()
        value[field] = bad
        with pytest.raises(ValueError):
            registry.admit(value)
    value = manifest()
    registry.admit(value)
    value["capabilities"].append("shell")
    assert registry.require("test-v1", "tag_events", 10)["capabilities"] == [
        "tag_events"
    ]
    for duration in (0, 11, float("nan"), float("inf"), True):
        with pytest.raises(ValueError):
            registry.require("test-v1", "tag_events", duration)


def test_evidence_separate_subject_and_bounds():
    evidence = dict(
        contract="earworm/analysis-evidence/v1",
        frame_id="frame",
        deployment_id="test-v1",
        model_revision="a" * 40,
        capability="tag_events",
        view=dict(
            asset_id="original",
            content_sha256="d" * 64,
            start_seconds=2,
            end_seconds=3,
            sample_rate_hz=48000,
            channels=2,
            transformations=["crop"],
        ),
        evidence_kind="model_hypothesis",
        confidence_kind="uncalibrated_score",
        result={"labels": []},
        limitations=[],
    )
    registry = DeploymentRegistry("test")
    registry.register_adapter("test", ["tag_events"], verify=lambda manifest: [])
    registry.admit(manifest())
    assert registry.validate_result("test-v1", evidence) == evidence
    evidence["view"]["end_seconds"] = 1
    assert contract_errors("analysis-evidence", evidence)


def test_schema_mirrors():
    root = Path(__file__).resolve().parents[2]
    for name in ("embedding-space", "model-deployment", "analysis-evidence"):
        assert json.loads(
            (root / "core/schemas" / f"{name}.schema.json").read_text()
        ) == json.loads(
            (root / "py-akousma/akousma" / f"{name}.schema.json").read_text()
        )


def test_cross_process_lock_cancel_nested_and_crash(tmp_path, monkeypatch):
    monkeypatch.setenv("LISTENINGSTACK_RESOURCE_DIR", str(tmp_path))
    code = "from akousma.resource_admission import heavy_lease; import time; "
    code += "\nwith heavy_lease('child', 'test'):\n print('acquired', flush=True)\n time.sleep(30)\n"
    child = subprocess.Popen(
        [sys.executable, "-c", code],
        stdout=subprocess.PIPE,
        text=True,
        env=os.environ.copy(),
    )
    try:
        assert child.stdout.readline().strip() == "acquired"
        assert admission_status()["busy"]
        with pytest.raises(TimeoutError):
            with heavy_lease("parent", "test", timeout=0.1):
                pass

        def cancelled():
            raise RuntimeError("cancelled")

        with pytest.raises(RuntimeError, match="cancelled"):
            with heavy_lease("parent", "test", checkpoint=cancelled):
                pass
    finally:
        child.kill()
        child.wait()
    with heavy_lease("parent", "test", timeout=1):
        assert admission_status()["busy"]
        with heavy_lease("parent", "nested", timeout=0.1):
            pass
    assert not admission_status()["busy"]


def test_manifest_cannot_admit_without_owner_verification():
    registry = DeploymentRegistry("test")
    registry.register_adapter(
        "test", ["tag_events"], verify=lambda manifest: ["weights missing"]
    )
    with pytest.raises(ValueError, match="weights missing"):
        registry.admit(manifest())
    assert registry.catalog() == []
