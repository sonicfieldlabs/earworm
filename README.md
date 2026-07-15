# Earworm

Earworm is a project-agnostic protocol and SDK for persistent listening in
agentic signal chains. It keeps audio events, intent, generation metadata,
analysis, user edits, agent actions, modulation, provenance, retention, and
render history in one queryable context chain.

Current release: `0.4.0`.

## Packages

| Package | Version | Purpose |
| --- | --- | --- |
| `@earworm/core` | 0.4.0 | Canonical TypeScript event/session types, schemas, event stores, state reconstruction, context queries, modulation, snapshots, and consent-gated manifest export. |
| `@earworm/sdk-js` | 0.4.0 | JavaScript client plus akousma record helpers. |
| `akousma` | 0.4.0 | Python reference store for sonic-memory records, objects, queries, lineage, kinship, location, covenants, change cursors, reindexing, and verification. |
| `earworm-sdk-python` | 0.4.0 | Read-only Python helpers for Earworm fixtures and sessions. |

## Protocol capabilities

- Append-only events with wall-clock, project, and asset-time references.
- In-memory and JSONL stores with deterministic state reconstruction.
- Prompt, generation, asset, signal, analysis, alignment, modulation,
  automation, agent-action, and snapshot event families.
- Context-bundle queries scoped by assets, event types, time ranges, and
  retention policy.
- Manifest export with provenance, redaction, consent, policy, and audit
  records.
- Cross-package conformance fixtures and runnable integration examples.

## Akousma memory

An **akousma** is an open sonic-memory record. Spec v1.3 supports:

- content-addressed audio objects and portable source references;
- producer-owned listening namespaces;
- causal lineage and typed kinship;
- tags, summaries, consent, rights, and provenance;
- consent-scoped `location` and directed `capture` metadata;
- listening covenants and attributed withholding;
- unknown top-level fields preserved for future producers.

The Python store implements `put`, `get`, filtered `query`, content-hash
recurrence, parents/children/ancestors/descendants, typed relations, tags,
locations, distance search, a tie-safe `changed_since` cursor, forget with
honest absence, reindex, and verify.

## Listening Stack compatibility

| Component | Version / contract | Relationship |
| --- | --- | --- |
| [AKOÚŌ](https://github.com/sonicfieldlabs/akouo) | `akouo/v0.7` | Defines the listening modes, evidence permissions, apparatus, memory-lineage output, and covenant shape stored by producers. |
| [OÍDA](https://github.com/sonicfieldlabs/oida) | 0.6.0 / `oida/gateway/v0.2` | Reference gateway. OÍDA-owned and host-owned perception emit the same Earworm event families and declare their apparatus. |
| [Akousmata](https://github.com/sonicfieldlabs/akousmata) | 0.4.0 | Reference navigator over the Python store. |
| [GERM](https://github.com/sonicfieldlabs/germ) | 0.2.0 | Writes lineage-bearing generations and Earworm context exports. |
| [Algophony](https://github.com/sonicfieldlabs/algophony) | 0.5.0 | Uses Earworm context and akousma relations for traceable batch evaluation. |
| [ORAM](https://github.com/sonicfieldlabs/oram) | 0.4.0 | Does not write the protocol directly; ORAM audio can be captured into akousma records by OÍDA or GERM. |

## Quick start

Requirements: Node.js 22+ and pnpm 10.32.1+.

```bash
pnpm install --frozen-lockfile
pnpm check
```

`pnpm check` validates fixtures, builds packages, runs JS and conformance
tests, type-checks, lints, validates manifests, and runs all examples.

Use the Python akousma store from this checkout:

```bash
uv run --project packages/py-akousma --extra dev pytest -q packages/py-akousma/tests
```

Minimal Python example:

```python
from akousma import AkousmataStore, new_akousma

with AkousmataStore("./listening-store") as store:
    record = new_akousma(
        audio={"asset_id": "asset_example", "uri": "objects/example.wav"},
        originating_app="example",
        source_type="generated",
        summary="A short metallic recurrence",
        tags=["metal", "loop"],
    )
    store.put(record)
```

## Repository layout

```text
packages/core/          canonical contracts and event-store primitives
packages/sdk-js/        JavaScript SDK and akousma helpers
packages/sdk-python/    read-only Python session helpers
packages/py-akousma/    Python akousma store
docs/                   protocol, concepts, API, governance, and ADRs
examples/               runnable integrations
tests/conformance/      shared conformance vectors
scripts/                validation, tests, examples, and export tools
```

## Documentation

- [Concept overview](docs/concepts/overview.md)
- [Core API](docs/api/core.md)
- [Akousma spec v1.3](docs/akousma_spec_v1.md)
- [Akousmata store](docs/akousmata-store.md)
- [OÍDA gateway integration](docs/oida-gateway.md)
- [Schemas](docs/schemas/index.md)
- [Provenance and policy](docs/governance/provenance-and-policy.md)
- [Architecture decision: schemas are canonical](docs/adr/0001-json-schema-is-canonical.md)
- [Changelog](CHANGELOG.md)

## License and trademarks

Code is licensed under MPL-2.0. See [LICENSE](LICENSE). Project names and
branding are handled separately; see [TRADEMARKS.md](TRADEMARKS.md).
