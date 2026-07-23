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

# Optional v1.4 accountable-listening index. The full producer report remains
# namespaced in `listening`; the auditum keeps attribution and references.
rec["auditum"] = akousma.auditum(listenings=[{
    "listening_id": "lst_1",
    "listener_id": "oida",
    "listener_type": "agent",
    "created_at": rec["created_at"],
    "report_namespace": "oida.signal",
    "contract": "akouo/v0.8",
}])

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
    store.query(has_auditum=True)          # accountable v1.4 records
    store.query(has_disagreement=True)     # plural hearings with preserved differences
```

The bundled `akousma/akousma.schema.json` is the canonical schema, kept in sync with
`earworm/packages/core/schemas/akousma.schema.json`.
