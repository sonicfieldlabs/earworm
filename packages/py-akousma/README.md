# akousma (Python)

Reference implementation of the Sonic Field **akousma** sonic-memory protocol. Consumed by
**oída**, **germ** (backend), and **algophony** (pipelines) so all three share one memory layer
with one lineage model.

Spec: [`earworm/docs/akousma_spec_v1.md`](../../docs/akousma_spec_v1.md) ·
Store: [`earworm/docs/akousmata-store.md`](../../docs/akousmata-store.md)

Source version 0.8.1 adds explicit Akousma 1.7/1.8 admission and the opt-in
spectral/native-evidence validators described in
[`spec/akousma-1.8.md`](../../spec/akousma-1.8.md). Existing constructors still
produce 1.6 records unless a host deliberately negotiates a newer contract.

Source version 0.8.2 adds `akousma.retained_policy`: one conservative covenant
projection for retained, untyped listening prose. Restrictions found at the top
level, in the auditum, in a native-policy extension or in a listening context are
combined, so moving a covenant never grants permission to text it restricted.

## Install

```sh
cd packages/py-akousma
pip install -e .
```

## Use

```python
import akousma

# Build + validate a record
rec = akousma.new_akousma(
    audio={"asset_id": "asset_1", "content_hash": "sha256:...", "duration_seconds": 10.0},
    originating_app="oida", source_type="recorded", origin="live-input",
    listening={"oida.signal": {"class": "music-like"}},
)
assert akousma.is_valid(rec)

# Optional v1.6 accountable-listening index. The full producer report remains
# namespaced in `listening`; the auditum keeps attribution and references.
rec["auditum"] = akousma.auditum(listenings=[{
    "listening_id": "lst_1",
    "listener_id": "oida",
    "listener_type": "agent",
    "created_at": rec["created_at"],
    "report_namespace": "oida.signal",
    "contract": "akouo/v0.9",
}], route_decisions=[akousma.route_decision(
    "decision-listen-1",
    gate="inference", outcome="proceed",
    subject="accountable listening pass",
    reason="The user requested an observe-only pass.",
    actor="oida-router", listening_id="lst_1",
    producer_contract="akouo/v0.9",
)])

# Shared store (platform application-data directory, or $AKOUSMATA_PATH)
with akousma.AkousmataStore() as store:
    uri = store.put_audio(open("clip.wav", "rb").read())   # content-addressed
    rec["audio"]["uri"] = uri
    store.put(rec)

    child = akousma.new_akousma(
        audio={"asset_id": "asset_2"}, originating_app="germ",
        source_type="generated", origin="generated",
        parent_akousma_ids=[rec["akousma_id"]], operation="transform", prompt="make it metallic",
    )
    store.put(child)
    store.ancestors(child["akousma_id"])   # -> [rec["akousma_id"]]  (germ lineage explorer)
    store.query(originating_app="oida")    # -> [rec]                (algophony batch)
    store.query(has_auditum=True)          # accountable records
    store.query(has_route_decision=True)   # auditum/v2 decisions
    store.query(has_stop_decision=True)    # refusal, withholding, forgetting, non-action...
    store.query(has_disagreement=True)     # plural hearings with preserved differences
    store.query(listener_type="human")     # exact attributable listener facet
    store.query(record_class="human")      # coarse navigator class
    store.current_head(rec["akousma_id"])  # unique latest revision, or raises on a branch
```

A refusal before capture is also addressable without inventing audio:

```python
refusal = akousma.new_akousma(
    originating_app="oida",
    source_type="unknown",
    origin="live-input",
    subject="quiet-hours capture request",
    auditum=akousma.auditum(route_decisions=[akousma.route_decision(
        "decision-capture-1",
        gate="capture", outcome="refuse", subject="audio capture",
        reason="The adopted covenant closes the ear.", actor="covenant-gate",
    )]),
)
```

A completed human listening may also remain addressable without inventing
audio. It needs an attributable listening and an explicit raw-audio absence:

```python
human = akousma.new_akousma(
    originating_app="akousmata",
    source_type="unknown",
    origin="live-input",
    subject="night insects heard from an open window",
    auditum=akousma.auditum(
        listenings=[{
            "listening_id": "lst_human_1",
            "listener_id": "local-listener-1",
            "listener_type": "human",
            "created_at": "2026-08-11T15:00:00Z",
            "report_namespace": "human.note",
            "contract": "akouo/v0.9",
        }],
        honest_absences=[{
            "id": "absence_raw_audio_1",
            "kind": "not_retained",
            "subject": "raw audio",
            "attributed_to": "local retention boundary",
            "listening_id": "lst_human_1",
        }],
        route_decisions=[akousma.route_decision(
            "decision_memory_1", gate="memory", outcome="proceed",
            subject="human listening account", reason="The listener chose to retain it.",
            actor="local-listener-1", listening_id="lst_human_1",
        )],
    ),
)
assert akousma.listener_types(human) == ("human",)
assert akousma.record_class(human) == "human"
```

`forget_with_receipt(...)` removes a record and returns a content-free durable
receipt. `forgotten(id)` can later prove the operation occurred without
restoring summary, tags, location, hashes, URIs, or forgotten content.

The bundled `akousma/akousma.schema.json` is the canonical schema, kept in sync with
`earworm/packages/core/schemas/akousma.schema.json`.

Unreleased opt-in listening helpers are available from
`akousma.listening_contracts`. See the repository's
[listening contract guide](../../docs/listening-contracts.md) for offline
validation, contract negotiation, and pass-to-listening adaptation.

The opt-in `akousma.record_evolution` module provides 1.7/v3 validation, scoped
reference checks, and retained-appeal promotion. See the
[unreleased draft](../../spec/akousma-1.7-draft.md). Default constructors remain 1.6.

The unreleased [observation-account binding and matter context](../../spec/observation-accounts.md) retain
MASA/AKOÚŌ source attribution, register/scale labels and non-acoustic distinctions.
JavaScript and Python APIs reuse injected foreign validators; local store writes
protect the retained mapping and independent context declarations.

The unreleased [agent sectors and measurement descriptors](../../spec/agent-sectors.md) reuse existing
rendering metadata and MASA source records. A conservative scalar comparison
checks compatible methods/units/windows; it performs no DSP or perceptual scoring.


## Local views and transformation graphs (unreleased)

The [auditum view](../../spec/auditum-view.md) checks explicit host permission
before record or receipt lookups. It distinguishes forgotten, unavailable and
withheld references, and excludes free-text receipt fields from the projection.
The Python store exposes `auditum_view`; the JavaScript SDK exports `auditumView`.

The [transformation graph](../../spec/transformation-graph.md) retains one MASA
source record and maps representations to explicit patch nodes with directed,
receipt-backed edges. Both SDKs require the host's actual MASA validator and
versioned direction registry. Graph accounts now use protected storage and explicit patch revisions. Typed
transposition receipts preserve separate rate/duration/band/hash declarations;
external engine execution remains downstream.
