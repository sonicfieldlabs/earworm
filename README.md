# Earworm

Earworm is a project-agnostic protocol and SDK for persistent listening in
agentic signal chains. It keeps audio events, intent, generation metadata,
analysis, user edits, agent actions, modulation, provenance, retention, and
render history in one queryable context chain.

This source candidate adds opt-in Akousma 1.9 representation contracts,
JavaScript packages 0.8.0, and Python `akousma` 0.9.0. Producer defaults remain
1.6. Publication and consumer activation are separate from source support.

## Packages

| Package | Version | Purpose |
| --- | --- | --- |
| `@earworm/core` | 0.8.0 source | Canonical TypeScript event/session and representation types, schemas, event stores, state reconstruction, context queries, and consent-gated manifest export. |
| `@earworm/sdk-js` | 0.8.0 source | JavaScript client, existing akousma helpers, and opt-in representation, output, lineage, and byte-admission validators. |
| `akousma` | 0.9.0 source | Python reference store, existing 1.7/1.8 admission, and opt-in representation/1.9 validation; representation-aware persistence remains downstream. |
| `earworm-sdk-python` | 0.7.0 | Read-only Python helpers for Earworm fixtures and sessions. |

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

An **akousma** is an open sonic-memory record. Spec v1.6 supports:

- content-addressed audio objects and portable source references;
- producer-owned listening namespaces;
- causal lineage and typed kinship;
- tags, summaries, consent, rights, and provenance;
- consent-scoped `location` and directed `capture` metadata;
- listening covenants and attributed withholding;
- zero or more attributable listenings per auditum, including their routes,
  pass/provenance references, influences, and contract references;
- addressable input, capture, inference, memory, output, disclosure, retention,
  and action decisions, including refusal before an audio asset exists;
- listening-only human or other attributable accounts without fabricated
  audio, provided raw-audio unavailability or non-retention is explicit;
- preserved disagreement, with an attributable note required before a
  disagreement is marked resolved;
- honest absence, scoped action authority and receipts, plus mechanically
  additive re-listening revisions that cannot overwrite an earlier account;
- explicit plural-listening versus ear-swarm declarations—parallelism alone
  never establishes a swarm;
- unknown top-level fields preserved for future producers.

The optional `auditum` block is the durable unit of accountable listening.
Here “tokenized” means structured, versioned, attributable, and addressable by
record id. It does not mean a financial or blockchain token. AKOÚŌ owns the
claim vocabulary; Earworm owns persistence, lineage, disagreement, authority,
absence, and revision.

The Python store implements `put`, `get`, filtered `query`, content-hash
recurrence, parents/children/ancestors/descendants, typed relations, tags,
locations, distance search, a tie-safe `changed_since` cursor, decision
queries, lossless listener-type and coarse record-class facets, branch-aware
revision heads, forget with content-free durable receipts, reindex, and verify.

## Listening Stack compatibility

| Component | Version / contract | Relationship |
| --- | --- | --- |
| [AKOÚŌ](https://github.com/sonicfieldlabs/akouo) | `akouo/v0.9` | Owns listening modes, claim attribution, context v2, provenance, passes, route decisions, ensembles, and covenant references. |
| [OÍDA](https://github.com/sonicfieldlabs/oida) | 0.10.0 / `oida/gateway/v0.6` | Reference producer. OÍDA keeps agent and human accounts attributable and persists them as linked, separately revisable akousmata. |
| [Akousmata](https://github.com/sonicfieldlabs/akousmata) | 0.7.0 | Reference navigator and accountability auditor over the Python store, including human-record revisions, listener facets, forgetting receipts, and true swarm semantics. |
| [GERM](https://github.com/sonicfieldlabs/germ) | 0.3.3 | Writes lineage-bearing generations and Earworm context exports. |
| [Algophony](https://github.com/sonicfieldlabs/algophony) | 0.5.2 | Uses Earworm context and akousma relations for traceable batch evaluation. |
| [ORAM](https://github.com/sonicfieldlabs/oram) | 0.4.1 | Does not write the protocol directly; ORAM audio can be captured into akousma records by OÍDA or GERM. |

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

Akousma 1.8 is an opt-in delivery contract. Consumers must explicitly admit
`1.8.0`; Earworm never strips its extensions, relabels it as 1.7, or treats an
unavailable host validator as accepted evidence. See
[`spec/akousma-1.8.md`](spec/akousma-1.8.md).

## Documentation

The [representation contract](spec/representation-records.md) supports text as
primary sonic material and a completed textual work as output. It keeps
representation, origin, access, role, terms, and time basis independently
identified. Python and JavaScript use the same canonical schemas and shared
synthetic conformance cases. Existing versioned schemas are retained.

- [Concept overview](docs/concepts/overview.md)
- [Core API](docs/api/core.md)
- [Akousma spec v1.6](docs/akousma_spec_v1.md)
- [Akousmata store](docs/akousmata-store.md)
- [OÍDA gateway integration](docs/oida-gateway.md)
- [Schemas](docs/schemas/index.md)
- [Provenance and policy](docs/governance/provenance-and-policy.md)
- [Architecture decision: schemas are canonical](docs/adr/0001-json-schema-is-canonical.md)
- [Changelog](CHANGELOG.md)

## What does not exist yet

- **A release of what this checkout adds.** The last public release is 0.7.0 (`v0.7.0`). The
  changelog's Unreleased section lists everything since, among it:
  - `akousma` 0.8.2 and its retained-covenant projection;
  - observation-account bindings;
  - agent sectors;
  - local views;
  - transformation graphs.
- **New versions by default.** Default constructors still write 1.6. Versions 1.7, 1.8 and 1.9
  require explicit consumer support. The existing store refuses 1.9 persistence until a
  representation-aware owner adapter is implemented.
- **An engine.** Earworm has no DSP engine and runs no transformation graph. Its graphs and recipes
  are contracts, and executing them is the application's work.
- **Writing from Python sessions.** `earworm-sdk-python` only reads.

## License and trademarks

Code is licensed under MPL-2.0. See [LICENSE](LICENSE). Project names and
branding are handled separately; see [TRADEMARKS.md](TRADEMARKS.md).

D5 local integration: [bundles](docs/bundles.md). Unreleased; no automatic publication.
