"""Canonical-store custody and owner permissions over synthetic inscriptions."""

from copy import deepcopy
from hashlib import sha256
import json
from pathlib import Path

import pytest
from akousma import AkousmataStore, new_akousma
from akousma.material_terms import MATERIAL_ACTIONS, MaterialTerms
from akousma.representation_store import (
    RepresentationStore,
    retained_representation_record,
)
from akousma.representations import REPRESENTATION_CONTRACTS

NOW = "2026-10-13T00:00:00Z"
ROOT = Path(__file__).resolve().parents[3] / "tests/contracts/representations"


@pytest.fixture
def owner(tmp_path):
    base = AkousmataStore(tmp_path)
    terms = MaterialTerms(base, actor_ref="fixture:owner", clock=lambda: NOW)
    terms.set(
        "fixture:terms:repository-license",
        actions=sorted(MATERIAL_ACTIONS),
        basis="Synthetic owned fixtures",
    )
    memory = RepresentationStore(base, authorize=terms.permit)
    block = json.loads((ROOT / "work.json").read_text())
    block["representations"][-1]["origin"]["kind"] = "generated"
    block["representations"][-1]["source_class"] = "generated_work"
    record = retained_representation_record(block, created_at=NOW)
    yield base, terms, memory, record
    base.close()


def put(memory, record):
    return memory.put(record, supported_contracts=REPRESENTATION_CONTRACTS)


def another(record, *, keep_source=True):
    value = deepcopy(record)
    block = value["extensions"]["earworm_representation"]
    mapping = {
        r["representation_id"]: r["representation_id"] + ":second"
        for r in block["representations"]
    }
    if keep_source:
        mapping.pop(block["representations"][0]["representation_id"])
    mapping.update(
        {
            block["record_ref"]: block["record_ref"] + ":second",
            block["operation_ref"]: block["operation_ref"] + ":second",
        }
    )

    def replace(item):
        if isinstance(item, str):
            return mapping.get(item, item)
        if isinstance(item, list):
            return [replace(v) for v in item]
        if isinstance(item, dict):
            return {k: replace(v) for k, v in item.items()}
        return item

    return replace(value)


def numbered(record, number, *, denied=False):
    """Distinct synthetic operations with explicit per-material terms."""
    block = record["extensions"]["earworm_representation"]
    mapping = {r["representation_id"]: f"fixture:representation:{number}:{i}"
               for i, r in enumerate(block["representations"])}
    mapping.update({block["record_ref"]: f"fixture:record:{number:04d}",
                    block["operation_ref"]: f"fixture:operation:{number:04d}"})
    if denied:
        mapping["fixture:terms:repository-license"] = "fixture:terms:hidden"
    def replace(item):
        if isinstance(item, str):
            return mapping.get(item, item)
        if isinstance(item, list):
            return [replace(v) for v in item]
        if isinstance(item, dict):
            return {k: replace(v) for k, v in item.items()}
        return item
    return replace(record)


def test_bounded_pages_cross_200_and_empty_withheld_pages_without_identity_leaks(owner):
    from akousma.representation_store import QUERY_SCAN_LIMIT
    base, terms, memory, record = owner
    terms.set("fixture:terms:hidden", actions=sorted(MATERIAL_ACTIONS), basis="Synthetic fixture")
    for number in range(820):
        put(memory, numbered(record, number, denied=number >= 250))
    previous = terms.get("fixture:terms:hidden")
    terms.set("fixture:terms:hidden", actions=[], basis="Withheld synthetic material",
              expected_revision=previous["revision"])
    queries = []
    base.conn.set_trace_callback(queries.append)
    page = memory.page(limit=200)
    assert page["records"] == [] and len(page["next_cursor"]) == 43
    assert "fixture:" not in canonical_page(page)
    cursor = page["next_cursor"]
    found = []
    while cursor:
        page = memory.page(limit=200, cursor=cursor)
        found += [r["akousma_id"] for r in page["records"]]
        cursor = page["next_cursor"]
    assert found == [f"fixture:record:{n:04d}" for n in range(249, -1, -1)]
    sql = [q for q in queries if q.startswith("SELECT a.akousma_id,a.created_at")]
    assert sql and all(f"LIMIT {QUERY_SCAN_LIMIT + 1}" in q for q in sql)
    plan = base.conn.execute("""EXPLAIN QUERY PLAN SELECT a.akousma_id,a.created_at FROM akousmata a
        WHERE json_extract(a.record,'$.record_kind')='representation_record'
        AND (a.created_at,a.akousma_id)<(?,?) ORDER BY a.created_at DESC,a.akousma_id DESC LIMIT ?""",
        (NOW, "fixture:record:0250", 513)).fetchall()
    assert any("idx_representation_order" in row["detail"] for row in plan)


def canonical_page(page):
    return json.dumps(page, sort_keys=True)


def test_continuation_checks_current_terms_filters_actor_audience_and_expiry(owner, monkeypatch):
    base, terms, memory, record = owner
    for number in range(3):
        put(memory, numbered(record, number))
    page = memory.page(limit=1, query="fixture:record:")
    cursor = page["next_cursor"]
    with pytest.raises(ValueError):
        memory.page(cursor=cursor, query="other")
    with pytest.raises(ValueError):
        memory.page(cursor=cursor, query="fixture:record:", audience="station-local")
    other = RepresentationStore(base, authorize=terms.permit, query_scope="other-owner")
    with pytest.raises(ValueError):
        other.page(cursor=cursor, query="fixture:record:")
    previous = terms.get("fixture:terms:repository-license")
    terms.set("fixture:terms:repository-license", actions=[], basis="Permission changed",
              expected_revision=previous["revision"])
    assert memory.page(cursor=cursor, query="fixture:record:")["records"] == []
    monkeypatch.setattr("akousma.representation_store.time.time", lambda: 10**12)
    with pytest.raises(ValueError, match="expired"):
        memory.page(cursor=cursor, query="fixture:record:")


def test_cursor_position_survives_forgetting_and_newer_insertions(owner):
    _, _, memory, record = owner
    for number in range(5):
        put(memory, numbered(record, number))
    page = memory.page(limit=2, output_kind="work", form="text")
    last = page["records"][-1]["akousma_id"]
    memory.forget(last, actor="fixture:owner", reason="Synthetic removal")
    new = numbered(record, 10)
    new["created_at"] = "2026-10-14T00:00:00Z"
    put(memory, new)
    rest = memory.page(limit=200, output_kind="work", form="text", cursor=page["next_cursor"])
    assert [r["akousma_id"] for r in rest["records"]] == [f"fixture:record:{n:04d}" for n in (2, 1, 0)]
    assert rest["next_cursor"] is None


def test_default_guard_and_explicit_store_dispatch_share_canonical_records(owner):
    base, _, memory, record = owner
    with pytest.raises(ValueError, match="adapter"):
        base.put(record)
    rid = base.put(
        record,
        representation_adapter=memory,
        supported_contracts=REPRESENTATION_CONTRACTS,
    )
    assert rid == record["akousma_id"] and base.get(rid) == memory.get(rid)
    assert put(memory, record) == rid
    assert (
        "inline_text"
        in record["extensions"]["earworm_representation"]["representations"][0][
            "artifact"
        ]
    )
    assert (
        "inline_text"
        not in memory.get(rid)["extensions"]["earworm_representation"][
            "representations"
        ][0]["artifact"]
    )
    audio = new_akousma(
        audio={"asset_id": "fixture:legacy"},
        originating_app="fixture",
        origin="file",
        source_type="designed",
    )
    base.put(audio)
    assert base.get(audio["akousma_id"]) and memory.get(audio["akousma_id"]) is None


def test_exact_bytes_and_immutable_record_and_representation_identities(owner):
    _, _, memory, record = owner
    put(memory, record)
    changed = deepcopy(record)
    changed["subject"] = "a different record"
    with pytest.raises(ValueError, match="immutable"):
        put(memory, changed)
    alias = another(record)
    alias["extensions"]["earworm_representation"]["representations"][0][
        "subject_ref"
    ] = "another subject"
    with pytest.raises(ValueError, match="identity"):
        put(memory, alias)
    assert len(memory.list()) == 1


def test_corrupt_artifact_aborts_admission_and_existing_corruption_is_detected(owner):
    base, _, memory, record = owner
    changed = deepcopy(record)
    changed["extensions"]["earworm_representation"]["representations"][0]["artifact"][
        "inline_text"
    ] = "wrong"
    with pytest.raises(ValueError):
        put(memory, changed)
    assert memory.list() == []
    put(memory, record)
    rep = record["extensions"]["earworm_representation"]["representations"][0]
    with base.conn:
        base.conn.execute(
            "UPDATE representation_objects SET bytes=? WHERE sha256=?",
            (b"wrong", rep["artifact"]["sha256"]),
        )
    with pytest.raises(ValueError, match="changed"):
        memory.read_bytes(rep["representation_id"])


def test_permissions_are_rechecked_inside_atomic_admission(owner):
    base, terms, _, record = owner

    def permit(action, rep, **kwargs):
        return not base.conn.in_transaction and terms.permit(action, rep, **kwargs)

    memory = RepresentationStore(base, authorize=permit)
    with pytest.raises(PermissionError):
        put(memory, record)
    assert (
        base.conn.execute("SELECT count(*) FROM representation_objects").fetchone()[0]
        == 0
    )
    assert base.get(record["akousma_id"]) is None


def test_failure_after_first_artifact_rolls_back_objects_members_and_record(owner):
    base, _, memory, record = owner
    put(memory, record)
    alias = another(record, keep_source=False)
    # First artifact is new, second aliases an existing identity with changed metadata.
    second = alias["extensions"]["earworm_representation"]["representations"][1]
    second["representation_id"] = record["extensions"]["earworm_representation"][
        "representations"
    ][1]["representation_id"]
    second["subject_ref"] = "fixture:changed"
    block = alias["extensions"]["earworm_representation"]
    old_ref = "fixture:account:second"
    for access in block["accesses"]:
        if access["representation_ref"] == old_ref:
            access.update(
                representation_ref=second["representation_id"],
                received_representation_ref=second["representation_id"],
            )
    for relation in block["relations"]:
        if relation["from_ref"] == old_ref:
            relation["from_ref"] = second["representation_id"]
    block["representations"][-1]["origin"]["source_refs"][1] = second[
        "representation_id"
    ]
    counts = [
        base.conn.execute("SELECT count(*) FROM " + t).fetchone()[0]
        for t in (
            "representation_artifacts",
            "representation_members",
            "representation_objects",
        )
    ]
    with pytest.raises(ValueError, match="identity"):
        put(memory, alias)
    assert counts == [
        base.conn.execute("SELECT count(*) FROM " + t).fetchone()[0]
        for t in (
            "representation_artifacts",
            "representation_members",
            "representation_objects",
        )
    ]


def test_derived_material_inherits_current_permissions_of_every_input(owner):
    _, terms, memory, record = owner
    block = record["extensions"]["earworm_representation"]
    block["representations"][1]["terms"]["ref"] = "fixture:account-terms"
    grant = terms.set(
        "fixture:account-terms",
        actions=sorted(MATERIAL_ACTIONS - {"export_public"}),
        basis="No public use of prior account",
    )
    put(memory, record)
    work = block["representations"][-1]["representation_id"]
    with pytest.raises(PermissionError):
        memory.read_bytes(work, action="export_public")
    terms.revoke("fixture:account-terms", expected_revision=grant["revision"])
    with pytest.raises(PermissionError):
        memory.read_bytes(work)
    assert memory.list() == []


def test_forgetting_keeps_shared_material_but_prevents_silent_resurrection(owner):
    base, _, memory, record = owner
    put(memory, record)
    second = another(record)
    put(memory, second)
    original = record["extensions"]["earworm_representation"]["representations"][0]
    receipt = memory.forget(
        record["akousma_id"], actor="fixture:owner", reason="fixture forgetting"
    )
    assert (
        "physical SQLite erasure is not established"
        in receipt["representation_cleanup"]
    )
    assert (
        sha256(memory.read_bytes(original["representation_id"])).hexdigest()
        == original["artifact"]["sha256"]
    )
    with pytest.raises(ValueError, match="resurrected"):
        put(memory, record)
    memory.forget(
        second["akousma_id"], actor="fixture:owner", reason="fixture forgetting"
    )
    with pytest.raises(KeyError):
        memory.read_bytes(original["representation_id"])
    third = another(second)
    with pytest.raises(ValueError, match="resurrected"):
        put(memory, third)
    assert (
        base.conn.execute("SELECT count(*) FROM representation_objects").fetchone()[0]
        == 0
    )


def test_legacy_forgetting_cannot_serve_or_resurrect_orphan_artifacts(owner):
    base, _, memory, record = owner
    put(memory, record)
    base.forget_with_receipt(record["akousma_id"])
    with pytest.raises(KeyError):
        memory.read_bytes("fixture:source")
    with pytest.raises(ValueError, match="resurrected"):
        put(memory, another(record))


def test_operation_identity_cannot_be_reused_even_after_forgetting(owner):
    _, _, memory, record = owner
    put(memory, record)
    memory.forget(record["akousma_id"], actor="fixture", reason="test")
    alias = another(record, keep_source=False)
    alias["extensions"]["earworm_representation"]["operation_ref"] = record[
        "extensions"
    ]["earworm_representation"]["operation_ref"]
    for item in (
        alias["extensions"]["earworm_representation"]["accesses"]
        + alias["extensions"]["earworm_representation"]["outputs"]
    ):
        item["operation_ref"] = alias["extensions"]["earworm_representation"][
            "operation_ref"
        ]
    with pytest.raises(ValueError, match="operation identity"):
        put(memory, alias)


def test_terms_compare_and_swap_and_utc_expiry(owner):
    _, terms, memory, record = owner
    old = terms.get("fixture:terms:repository-license")
    with pytest.raises(ValueError, match="changed"):
        terms.set(
            old["terms_ref"], actions=[], basis="stale", expected_revision="fictional"
        )
    for boundary in (
        "2026-10-12T00:00:00Z",
        "2026-10-14T00:00:00",
        "2026-10-14T00:00:00-05:00",
    ):
        with pytest.raises(ValueError, match="UTC"):
            terms.set(
                old["terms_ref"],
                actions=old["actions"],
                basis="expiry",
                expected_revision=old["revision"],
                expires_at=boundary,
            )
    terms.set(
        old["terms_ref"],
        actions=old["actions"],
        basis="expiry",
        expected_revision=old["revision"],
        expires_at="2026-10-14T00:00:00Z",
    )
    put(memory, record)
    terms.clock = lambda: "2026-10-14T00:00:00Z"
    with pytest.raises(PermissionError):
        memory.read_bytes("fixture:source")


def test_terms_missing_parents_and_cycles_fail_closed(owner):
    _, terms, _, record = owner
    work = deepcopy(
        record["extensions"]["earworm_representation"]["representations"][-1]
    )
    assert not terms.permit("read", work)
    work["origin"]["source_refs"] = [work["representation_id"]]
    assert not terms.permit("read", work, resolve_representation=lambda _: work)
