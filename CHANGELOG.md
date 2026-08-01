# Changelog

## 0.6.0 — Decision-first auditums

- Advanced the open akousma record to spec v1.5 and the current accountable
  block to `earworm/auditum/v2`, while retaining validation compatibility for
  every earlier v1 record and `earworm/auditum/v1` fixture.
- Added addressable route decisions across input, capture, inference, memory,
  output, disclosure, retention, and action gates.
- Added decision-only akousmata: an input or capture refusal can carry a safe,
  category-level subject without fabricating audio or a listening pass.
- Added pass, listening-provenance, and producer-decision references on
  attributable listenings, plus expanded participant types.
- Distinguished plural listening from an ear swarm. A swarm requires declared
  influence, preserved permissions and disagreements, and a dissolution rule.
- Removed epistemic `undetermined` from current honest-absence kinds; it
  remains a producer claim category rather than an attributed availability or
  permission state.
- Added indexed route/stop decision queries to the Python store.
- Added content-free durable forgetting receipts, receipt lookup, shared-audio
  outcomes, and protection against silently resurrecting a forgotten id.
- Added a pre-capture refusal fixture and cross-language JS/Python tests.
- Bumped all Earworm packages to `0.6.0`.

## 0.5.0 — Addressable auditums

- Added akousma spec v1.4's `auditum` block: attributable listening routes,
  preserved disagreement, honest absence, scoped action authority and
  receipts, and additive revision lineage.
- Added matching Python and JavaScript builders, TypeScript declarations,
  shape validation, fixtures, and indexed store queries.
- Added semantic listening, disagreement, action, revision, and forgetting
  event families plus context-selector groups.
- Strengthened the fixture harness to resolve internal schema references and
  validate constants, nullable types, minimum lengths, and uniqueness.
- Clarified ownership: AKOÚŌ owns claim semantics; Earworm owns durable,
  addressable listening history. “Tokenized” is structural, never financial.

## 0.4.0 — Covenant-aware memory

- Added akousma spec v1.3 covenant identity, lineage, commitments, and
  attributed withholding.
- Added `covenant_id` filtering and indexed in-place store migration.

## 0.3.0 — Location and directed capture

- Added consent-scoped location, past/future/live capture metadata, open
  top-level records, map queries, and store fast paths.

## 0.2.2 — Provider-neutral gateway context

- Documented OÍDA-owned and host-owned perception with explicit apparatus
  provenance.
- Added a tie-safe store change cursor.

## 0.2.1 — Navigator surface

- Added tag aggregation, change watching, forget with honest absence, and the
  operations required by the Akousmata navigator.

## 0.2.0 — Akousma memory

- Added the open sonic-memory record, Python store, lineage, kinship, context,
  and consent-gated export.

## 0.1.0 — Earworm protocol

- Published the event/session protocol, stores, queries, state reconstruction,
  modulation, automation, manifests, SDKs, fixtures, and conformance tooling.
