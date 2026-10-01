# Changelog

## Unreleased

- Pin fast-uri 3.1.8 in JavaScript tooling to address the authority and host-normalization advisories.

- Package py-akousma 0.8.4 with atomic audio publication; record schemas stay unchanged.
- Publish Python audio objects atomically from verified, synced private staging
  files. Interrupted writes never expose partial canonical objects; concurrent
  writers deduplicate without overwriting existing data. Object identities,
  record schemas and forgetting receipts are unchanged.

- py-akousma 0.8.3: restrict sharded object locators to canonical SHA-256 names,
  refuse symlinks below the selected store root and mismatched object bytes,
  validate extensions before writes, and bind audio forgetting to its declared
  content hash. Records sharing an object locator preserve it even if their
  declared hash differs. No record schema or forgetting-receipt change.

- py-akousma 0.8.2: added `akousma.retained_policy` (`retained_covenant`,
  `blocks_untyped_prose`). Covenant restrictions from every location a producer
  may write them are combined cumulatively; a restricted consent status adds
  `do_not_reveal`. GERM and Oída use it to decide whether retained prose may be
  shown or reused. No schema change.

- Added a portable six-scenario listening matrix composed from existing local
  fixtures, shared JS/Python negative cases, legacy-reader checks and store
  reopen/reindex preservation. Canonical generation is checked for drift.

- Added protected graph artifact storage, explicit +1 patch revisions through the
  existing revision index, and actual MASA validation required on graph writes.
- Added versioned transposition receipt recipes for filtered resampling,
  playback-rate changes, frequency translation and MASA pitch shifting, with
  separate rates, windows, bands, duration behavior, engine and integrity checks.
  No DSP engine or MASA namespace term was introduced.

- Added permission-aware local auditum views with allowlisted forgetting receipt
  metadata, explicit unavailable/withheld states and one-hop record references.
  Reused existing forgetting/store reads without changing retained evidence.
- Added standalone application transformation graph contracts and JS/Python APIs,
  reusing host MASA validation, direction registry, source records and receipts.
  These are now complemented by protected graph records and typed recipes;
  engine execution remains application work. No new MASA namespace terms or DSP.

- Added opt-in agent sectors with listening-scoped claim/rendering references and
  separate acoustic/non-acoustic access bindings, plus detached local views.
- Added source-preserving MASA measurement descriptors for centroid, band energy,
  level and duration, and a conservative absolute-difference relation with
  recomputation from explicit record/descriptor references. Reused store/reindex
  and protected revision behavior; no DSP or MASA namespace promotion.

- Added opt-in observation-account storage bindings and MASA 0.2.0 matter context,
  with JavaScript/Python constructors, foreign-validator callbacks, shared
  fixtures and independent source/representation/access/temporal semantics.
- Protected retained observation mappings and context declarations through store
  writes/reindexing; fixed boolean/numeric equality in protected JSON evidence.

- Added an opt-in 1.7/v3 draft schema, generated from the unchanged released
  schema plus explicit evolution definitions; default constructors remain 1.6.
- Added negotiated, source-preserving appeal promotion, versioned typed
  relations, research proposals and non-executing generation decisions.
- Added scoped reference/chronology validation, complete relation-detail reads,
  protected evolution/legacy-appeal evidence and shared JS/Python fixtures.

- Added `earworm/listening-context/v1` for subjects, recipients, report format,
  rendering provenance, and independent claim currency/retention declarations.
  JS/Python helpers validate record-local references and deterministic expiry.
- Required explicit channel counts and model blind spots in the unreleased
  access contract; protected stored context evidence and reused forgetting receipts.

- Added opt-in `earworm/listening-access/v1` declarations, offline JavaScript and
  Python validation, and explicit required-contract negotiation. Existing
  akousma 1.6 and auditum/v2 records retain their formats.
- Added an AKOÚŌ pass-to-listening adapter with an explicit one-to-one ID map,
  source preservation, listener taxonomy, and ensemble influence checks.
- Protected access declarations and retained pass adapters against in-place
  changes in the Python store; malformed access declarations are rejected.
- Added shared positive and negative fixtures and Python CI coverage.

## 0.7.0 — Attributable human listening

- Advanced the open akousma record to spec v1.6 while retaining
  `earworm/auditum/v2` and validation compatibility for earlier v1 records.
- Added listening-only akousmata: audio may be omitted only with a non-empty
  subject, at least one attributable listening, and an honest absence stating
  that raw audio was unavailable or not retained. Decision-only records remain
  distinct and require an empty listening list plus a pre-capture stop.
- Added lossless `listener_types` / `listenerTypes` facets and coarse
  `record_class` / `recordClass` navigation helpers. Community, institutional,
  sensor, habitat, other-animal, ensemble, and other listening are preserved
  rather than collapsed into human or agent categories.
- Added indexed listener-type, record-class, and direct-revision queries to
  the Python store, plus branch-aware revision-chain, head, and unique-current-
  head helpers.
- Migrated and reindexed existing SQLite stores in place without rewriting
  canonical record JSON, and retained protected-account immutability for human
  and machine-authored records alike.
- Added a shared listening-only fixture and Python/JavaScript parity tests.

## 0.6.1 — Revision integrity

- Required a non-empty resolution note whenever an attributable disagreement
  is marked resolved, across the canonical schema and both SDK validators.
- Protected stored listening, auditum, provenance-account, and causal-lineage
  fields from silent in-place replacement while retaining app-owned curatorial
  edits.
- Required a revision record to use a fresh id and point to an existing record
  in the same store.
- Expanded environment-file ignore coverage and added cross-language
  regression tests.

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
