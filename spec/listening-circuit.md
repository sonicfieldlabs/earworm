# Listening circuits and run memory — unreleased draft

`earworm/listening-circuit/v1` records the moves a listening loop made around one record, and
`earworm/run-memory/v1` what a run remembers of itself while it lasts. Both are additive: any
akousma spec version may carry the circuit as `extensions.earworm_listening_circuit`, and a reader
that does not negotiate the contract preserves it as an unknown extension. No released schema
changed.

## Why a circuit is its own record

The auditum's `route_decisions` are gates: whether a listening may proceed, be withheld,
forgotten or not acted on. A circuit records something else: which move a loop chose next, among
the moves it was offered. The two meet when a gate refuses a move; the step's outcome then says
`refused` and names the reason, and the gate keeps its own entry.

## A step

| Field | Meaning |
| --- | --- |
| `move` | `relisten_same` (the same retained fragment, another mode, model or question), `new_fragment` (a new window of the same source), `switch_source`, `sound` (a generation from the listening), `reason`, `retrieve`, `analyze`, `stop` |
| `offered`, `chosen` | Every candidate the decider was shown, by id, with its move and the producer's own action name; the chosen id must be one of them, with the same move. Only a stop or an unexecuted step may choose nothing. |
| `decider` | `router` (a deterministic listening router such as AKOÚŌ's), `rules`, `reasoner` (a model), `operator` or `score`; its provider, model, the decider asked first when this one decided by fallback, the producer's decision journal reference and the rules that bounded it. |
| `route` | What the router read: primary, secondary and corrective ears, confidence, the coarse kinds it heard (`heard_as`, an attributed reading, not a measurement), the preset it maps to and the router's identity. |
| `reasoning`, `alternative_reading` | Why, and the reading that was kept alive beside it. Producers must not put transcripts or withheld subjects here. |
| `layer`, `depth` | `general`, `focused`, `corrective`, `sounding` (the move that sounds), `recall` or `closing` (a stop); depth counts recursion through soundings and may not exceed `bounds.max_depth`. |
| `from_listening_id`, `to_listening_id`, `to_akousma_id` | A re-listening lands in this record's auditum; a new fragment, a switch or a sounding lands in another record, which an executed step must name. With a record, listening ids must resolve to its auditum. |
| `bounds`, `outcome` | Remaining budgets and the station rule that applied; `proposed`, `executed`, `refused`, `blocked` or `failed`, with a reason. |

## Run memory

A run memory is folded one window at a time from the circuits (`fold_run_memory` /
`foldRunMemory`, pure and deterministic, with parity between Python and JavaScript on
`tests/contracts/circuit`). Per source it keeps when it was first and last heard, windows, visits
(a return after another source is a new visit), dwell (windows in the current stay), the run's
window count when it was last heard (for cooldowns, `windows_since`), the kinds and modes it was
heard as, declined and repeated counts, soundings and the last route. It also keeps totals by move
and layer and the last 64 moves. It never carries audio, account text or transcripts, and it
refuses circuits from another run or source and windows folded out of time order.

## Use

```python
from akousma.listening_circuit import listening_circuit_errors, empty_run_memory, fold_run_memory

errors = listening_circuit_errors(record["extensions"]["earworm_listening_circuit"], record)
memory = empty_run_memory(session_id, started_at)
memory = fold_run_memory(memory, at=at, source_key=key, akousma_id=record["akousma_id"],
                         circuit=record["extensions"]["earworm_listening_circuit"],
                         heard_as=["music"], modes=["caption", "music"])
```

JavaScript exports `listeningCircuitErrors`, `circuitRecordErrors`, `runMemoryErrors`,
`emptyRunMemory`, `foldRunMemory` and `windowsSince` with the same behaviour.
