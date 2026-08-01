# akousma (Python)

Reference implementation of the Sonic Field **akousma** sonic-memory protocol. Consumed by
**oída**, **germ** (backend), and **algophony** (pipelines) so all three share one memory layer
with one lineage model.

Spec: [`earworm/docs/akousma_spec_v1.md`](../../docs/akousma_spec_v1.md) ·
Store: [`earworm/docs/akousmata-store.md`](../../docs/akousmata-store.md)

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

# Optional v1.5 accountable-listening index. The full producer report remains
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

`forget_with_receipt(...)` removes a record and returns a content-free durable
receipt. `forgotten(id)` can later prove the operation occurred without
restoring summary, tags, location, hashes, URIs, or forgotten content.

The bundled `akousma/akousma.schema.json` is the canonical schema, kept in sync with
`earworm/packages/core/schemas/akousma.schema.json`.
