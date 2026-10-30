import json
from copy import deepcopy
from pathlib import Path

import pytest

from akousma.listening_circuit import (
    LISTENING_CIRCUIT_CONTRACT,
    RECENT_LIMIT,
    circuit_record_errors,
    empty_run_memory,
    fold_run_memory,
    listening_circuit_errors,
    run_memory_errors,
    windows_since,
)

FIXTURES = Path(__file__).resolve().parents[3] / "tests" / "contracts" / "circuit"


def read(name):
    return json.loads((FIXTURES / f"{name}.json").read_text())


def mutate(value, path, new):
    target = value
    for key in path[:-1]:
        target = target[key]
    target[path[-1]] = new


def test_the_shared_circuit_and_its_record_are_valid():
    fixture = read("circuit")
    assert fixture["circuit"]["contract"] == LISTENING_CIRCUIT_CONTRACT
    assert listening_circuit_errors(fixture["circuit"]) == []
    assert listening_circuit_errors(fixture["circuit"], fixture["record"]) == []
    assert circuit_record_errors(fixture["record"]) == []
    assert circuit_record_errors({"extensions": {}}) == []


@pytest.mark.parametrize("case", read("cases"), ids=lambda c: c["name"])
def test_shared_cases(case):
    fixture = read("circuit")
    circuit = deepcopy(fixture["circuit"])
    mutate(circuit, case["path"], case["value"])
    for extra in case.get("also", []):
        mutate(circuit, extra["path"], extra["value"])
    assert (listening_circuit_errors(circuit, fixture["record"]) == []) is case["valid"]


def test_a_record_without_listenings_cannot_carry_a_circuit():
    fixture = read("circuit")
    assert listening_circuit_errors(fixture["circuit"], {"akousma_id": "x"}) != []


def test_folding_matches_the_shared_expectation_and_is_pure():
    fold = read("fold")
    circuit = read("circuit")["circuit"]
    before = deepcopy(circuit)
    memory = empty_run_memory(fold["session_id"], fold["started_at"])
    start = deepcopy(memory)
    for step in fold["inputs"]:
        args = dict(step)
        if args.pop("circuit", False):
            args["circuit"] = circuit
        memory = fold_run_memory(memory, **args)
    assert memory == fold["expected"]
    assert circuit == before
    assert start == empty_run_memory(fold["session_id"], fold["started_at"])
    assert run_memory_errors(memory) == []
    assert windows_since(memory, "locustream_2020") == 1
    assert windows_since(memory, "never-heard") is None


def test_a_return_to_a_source_is_a_new_visit_and_dwell_counts_the_stay():
    memory = empty_run_memory("ses_a", "2026-10-30T00:00:00Z")
    for minute, source in enumerate(["a", "a", "a", "b", "a"], start=1):
        memory = fold_run_memory(memory, at=f"2026-10-30T00:0{minute}:00Z", source_key=source)
    a = memory["sources"]["a"]
    assert (a["windows"], a["visits"], a["dwell"]) == (4, 2, 1)
    assert memory["sources"]["b"]["visits"] == 1
    assert memory["current_source"] == "a"


def test_folding_refuses_other_runs_other_sources_and_time_running_back():
    circuit = read("circuit")["circuit"]
    memory = empty_run_memory("ses_other", "2026-10-30T00:00:00Z")
    with pytest.raises(ValueError, match="another run"):
        fold_run_memory(memory, at="2026-10-30T03:05:00Z", source_key="locustream_1010", circuit=circuit)
    memory = empty_run_memory(circuit["run"]["session_id"], "2026-10-30T00:00:00Z")
    with pytest.raises(ValueError, match="another source"):
        fold_run_memory(memory, at="2026-10-30T03:05:00Z", source_key="elsewhere", circuit=circuit)
    memory = fold_run_memory(memory, at="2026-10-30T03:05:00Z", source_key="x")
    with pytest.raises(ValueError, match="time order"):
        fold_run_memory(memory, at="2026-10-30T03:04:00Z", source_key="x")


def test_recent_moves_are_bounded():
    memory = empty_run_memory("ses_b", "2026-10-30T00:00:00Z")
    for n in range(RECENT_LIMIT + 10):
        memory = fold_run_memory(memory, at=f"2026-10-30T{n // 60:02d}:{n % 60:02d}:00Z", source_key="s")
    assert len(memory["recent"]) == RECENT_LIMIT
    assert memory["totals"]["windows"] == RECENT_LIMIT + 10


def test_run_memory_never_carries_text_or_audio():
    memory = empty_run_memory("ses_c", "2026-10-30T00:00:00Z")
    memory = fold_run_memory(memory, at="2026-10-30T00:01:00Z", source_key="s")
    for key, value in (("transcript", "words"), ("audio", "raw.wav")):
        bad = deepcopy(memory)
        bad["sources"]["s"][key] = value
        assert run_memory_errors(bad) != []
    bad = deepcopy(memory)
    bad["current_source"] = "unheard"
    assert run_memory_errors(bad) != []


# --- the store keeps circuits and run memories ----------------------------------------------

import akousma  # noqa: E402


def _record_with_circuit(circuit, ids=("lst_1", "lst_2", "lst_3")):
    listenings = [
        {
            "listening_id": lid,
            "listener_id": "oida",
            "listener_type": "agent",
            "created_at": "2026-10-30T03:00:00Z",
            "report_namespace": f"oida.{lid}",
            "contract": "akouo/v0.9",
        }
        for lid in ids
    ]
    auditum = akousma.auditum(
        listenings=listenings,
        honest_absences=[{
            "id": "absence-raw", "kind": "not_retained", "subject": "raw audio",
            "attributed_to": "local retention boundary", "listening_id": ids[0],
        }],
        route_decisions=[akousma.route_decision(
            "decision-lst_1", gate="inference", outcome="proceed", subject="listening pass",
            reason="The run admitted this window.", actor="test", listening_id=ids[0],
            producer_contract="akouo/v0.9",
        )],
    )
    return akousma.new_akousma(
        originating_app="test", subject="a radio window", auditum=auditum,
        session_id=circuit["run"]["session_id"],
        extensions={"earworm_listening_circuit": circuit},
    )


def test_the_store_validates_indexes_protects_and_forgets_circuits(tmp_path):
    circuit = read("circuit")["circuit"]
    store = akousma.AkousmataStore(tmp_path / "store")
    record = _record_with_circuit(circuit)
    rid = store.put(record)
    steps = store.circuit_steps(session_id=circuit["run"]["session_id"])
    assert [s["step_id"] for s in steps] == ["stp_0", "stp_1", "stp_2", "stp_3"]
    assert {s["akousma_id"] for s in steps} == {rid}
    assert [s["move"] for s in store.circuit_steps(source_key="locustream_1010", move="sound")] == ["sound"]
    assert steps[1]["primary_mode"] == "musical-aesthetic-listening" and steps[1]["decider"] == "akouo"

    bad = deepcopy(record)
    bad["akousma_id"] = "akm_bad"
    bad["extensions"]["earworm_listening_circuit"]["steps"][1]["chosen"] = "elsewhere"
    with pytest.raises(ValueError, match="not offered"):
        store.put(bad)

    rewritten = deepcopy(record)
    rewritten["extensions"]["earworm_listening_circuit"]["steps"][1]["reasoning"] = "A later story."
    with pytest.raises(ValueError, match="existing listening account"):
        store.put(rewritten)

    store.conn.execute("DELETE FROM circuit_steps")
    store.conn.commit()
    store.reindex()
    assert len(store.circuit_steps()) == 4

    store.forget(rid, actor="test", reason="test forgetting")
    assert store.circuit_steps() == []
    store.close()


def test_an_existing_store_gains_the_circuit_index_when_opened(tmp_path):
    circuit = read("circuit")["circuit"]
    store = akousma.AkousmataStore(tmp_path / "store")
    store.put(_record_with_circuit(circuit))
    store.conn.execute("DROP TABLE circuit_steps")
    store.conn.commit()
    store.close()
    reopened = akousma.AkousmataStore(tmp_path / "store")
    assert len(reopened.circuit_steps()) == 4
    reopened.close()


def test_run_memories_are_compare_and_set(tmp_path):
    store = akousma.AkousmataStore(tmp_path / "store")
    memory = empty_run_memory("ses_store", "2026-10-30T00:00:00Z")
    with pytest.raises(ValueError, match="only moves forward|revision"):
        store.put_run_memory(memory, expected_revision=0)
    store.put_run_memory(memory, expected_revision=None)
    later = fold_run_memory(memory, at="2026-10-30T00:01:00Z", source_key="s")
    store.put_run_memory(later, expected_revision=0)
    assert store.run_memory("ses_store") == later
    with pytest.raises(ValueError, match="revision 1, not 0"):
        store.put_run_memory(fold_run_memory(memory, at="2026-10-30T00:02:00Z", source_key="t"), expected_revision=0)
    with pytest.raises(ValueError, match="only moves forward"):
        store.put_run_memory(memory, expected_revision=1)
    bad = deepcopy(later)
    bad["sources"]["s"]["transcript"] = "words"
    with pytest.raises(ValueError, match="invalid run memory"):
        store.put_run_memory(bad, expected_revision=1)
    assert store.run_memories()[0]["windows"] == 1
    assert store.run_memory("unknown") is None
    store.close()
