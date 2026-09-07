# Akousma 1.7 / auditum v3 — opt-in, unreleased draft

This draft adds accountable appeals, versioned relations, research proposals and
generation decision proposals, and structured observation accounts. Released akousma 1.6 and `earworm/auditum/v2` remain
unchanged. Package versions have not advanced and no release is implied.

Producers and consumers MUST negotiate `earworm/akousma/v1.7`; an auditum-bearing
record also requires `earworm/auditum/v3`. A record identifies `schema_version:
"1.7.0"`. The new validator uses the standalone
[`akousma-1.7.schema.json`](../packages/core/schemas/akousma-1.7.schema.json).
Default constructors still produce released 1.6 records. Never insert new relation
kinds or `auditum.appeal` into a record still labelled 1.6/v2.

The draft schema is generated from the released schema plus
[`record-evolution.schema.json`](../packages/core/schemas/record-evolution.schema.json)
by `node scripts/generate-next-schema.mjs`. Edit the definitions/generator, then
run that command and `node scripts/sync-akousma-schema.mjs`. `pnpm check` detects a
stale generated schema. Python wheels bundle the complete standalone schema;
validation performs no remote schema retrieval.

## Appeal and retained evidence

`auditum.appeal` uses `earworm/appeal/v1`. It records an identity, recording actor,
subjects, reason, workflow status, evidence references, and an explicit resolution
reference/reason when resolved. A workflow status is not a confidence score or
permission to act. An imported legacy source identifies the source record and
`/extensions/oida/appeal`, retaining its entire JSON payload.

`promoteLegacyAppeal(record, options)` and `promote_legacy_appeal(record, options)`
require explicit supported contracts, fresh record/revision IDs, recording actor,
subjects, reason and timestamp. They return a new revision; the source, its unknown
fields, original listening accounts, causal parents and legacy payload remain
unchanged. The adapter does not assume a legacy payload schema or interpret its
status. Imported appeals begin `unreviewed`, including a legacy payload claiming
approval. It refuses absent payloads, an already-promoted appeal, reused record
IDs, unsupported contracts, and revision times preceding the source.

The source must have an attributable auditum with route decisions. The adapter
does not invent a hearing, authority or missing route decision to upgrade an
incomplete account. Source timestamps must support the documented UTC chronology
checks. Imported material remains subject to the host's disclosure policy; opaque
preservation is not approval to expose its contents.

## Typed relations

New relations stay in `lineage.relations`. Each carries
`contract: "earworm/relations/v1"`, a record-local `relation_id`, target record,
declaring actor, evidence references, epistemic status and separate review state.
The initial kinds are `report_of`, `research_for`, `decision_on`, `observed_from`,
`mapped_from` and `similar_by`. Released relation kinds remain available unchanged.
Unknown/new kinds cannot be squeezed into a released closed enum.

Causal parents remain in `lineage.parent_akousma_ids`. A `report_of` link does not
assert same-source sound identity or influence. Influence remains attributable
between listening accounts through the existing listening/ensemble fields. A
similarity relation does not create causal parenthood or assert that an ensemble
exists. Self-targeting new relations and duplicate relation identities are invalid.

A `similar_by` relation requires a criterion: feature and units, method reference
and revision, explicit inputs including its target, normalization, and a qualified
score. A known score carries its score policy; unknown/unavailable/not-applicable
scores retain their reason. Review and epistemic status stay separate. A proposal
with an uncomputed score is not evidence that two records are similar. The opt-in [measurement descriptors and scalar comparison](agent-sectors.md) now
bind MASA measurements to two record/descriptor references and recompute an
absolute difference. Measurement engines and physical/perceptual evaluation remain
separate work; this application vocabulary promotes no new MASA term.

The existing relation edge index is reused. `relations()` and `related()` retain
their coarse compatibility behavior. `relation_details()` reads complete metadata
from the canonical record. Multiple criteria for one type/target may share a coarse
index edge while retaining distinct relation IDs and full payloads. Reindexing
must not rewrite records or collapse those distinct proposals.

## Research proposals

`record_kind: "research_proposal"` requires
`extensions.earworm_research` with `earworm/research/v1`: proposal identity, author,
question, source/evidence references, proposed relation IDs and independent review.
Proposed relation IDs must resolve within the record. A research proposal may be
audio-less without fabricating an asset or a pre-capture refusal.

The existing `provenance.source_type` enum remains closed; `research` is invalid.
Use a released source type only when its meaning is accurate, and use explicit
`unknown` when no released category establishes the source classification. The
record kind describes the proposal; it does not turn research into a recording.
External sources, evidence and policy references still require host resolution.

## Generation decisions

`record_kind: "generation_decision"` requires
`extensions.earworm_generation_decision` with `earworm/generation-decision/v1`.
It records the generation, subsequent listening record/listening references,
keep/revise/discard/variation outcome, actor, reason, policy and revision, inputs,
next-job proposal and stop outcome. Its `decision_on` relation identifies the same
generation. All generation/listening record inputs remain explicit.

Keep/discard cannot schedule a next job. Continuing requires an explicit planned
job; stop/defer must have no next job. `execution` is `not_requested`: this record
neither starts a worker nor grants action authority. Confirmation, scoped runtime
authority, retention and publication gates remain the consuming application's
responsibility. Declaring a proposal confirmed elsewhere cannot bypass them.

The reference checker requires a generated record, resolves each subsequent
listening in its source account, and checks generation → listening → decision
chronology from declared UTC timestamps. It does not prove those events happened.
A research or decision proposal can remain an artifact without pretending that a
new listening pass occurred merely because the proposal was written.

## Validation, references and storage

`nextRecordErrors` / `next_record_errors` validate structure and record-local
semantics, including auditum attribution, duplicates, relation IDs, proposal
references and decision consistency. `akousmaShapeErrors` and Python
`validation_errors` dispatch to the draft validator for exactly version 1.7.0.
Record classification helpers retain their existing coarse purpose; consumers
should inspect `record_kind` for these new artifact families.

`nextRecordReferenceErrors(record, records)` /
`next_record_reference_errors(record, records)` use an explicit array of complete
records. They reject ambiguous scope IDs, malformed referenced records, missing
record-valued links, a changed imported appeal payload, unresolved subsequent
listenings, and impossible declared chronology. They do not fetch external
references or establish the truth of a cited document or a physical measurement.

The store permits unresolved cross-record links for archival/import purposes,
consistent with its existing behavior. Resolve the required scope before relying
on a decision or relation. `verify()` continues to surface dangling kinship,
parent and revision links. Missing/forgotten records must remain unavailable;
neither a schema-valid reference nor an index edge restores them.

The Python store protects typed evolution relations, record kind, research and
decision payloads, canonical appeals, and the retained legacy `extensions.oida.appeal`
against in-place addition, deletion or replacement. Other curatorial oída extension
metadata retains its ordinary behavior. Changes to protected evidence require a
new record and revision relationship; a proposal must not overwrite its source.

Older readers may reject closed v3 fields or merely preserve unfamiliar open
fields. Successful legacy validation is not evidence of negotiated support.
There is no automatic downgrade that drops relation metadata, rewrites provenance,
or moves a proposal into a fabricated audio/listening record.


## Observation accounts and matter context

The opt-in [observation-account binding](observation-accounts.md) now retains a
validated MASA/AKOÚŌ mapping in one namespaced listening payload. Its explicit
artifact kind requires no fabricated audio or absence. Matter context preserves
source register/scale labels separately from source modality, representation,
temporal evidence domain and the existing access declaration. New validators and
constructors are available in JavaScript and Python; the store protects these
bindings and distinguishes boolean from numeric values in retained evidence.


## Agent sectors

The opt-in [agent-sector and measurement-set extensions](agent-sectors.md) now
resolve attributable claim and rendering references, independent access limits,
and explicit MASA scalar descriptors. Rendering metadata stays in listening
context. Local storage protects sector/mapping evidence and typed comparison
criteria; referenced descriptor comparisons are recomputed against retained inputs.


## Graph artifacts

The [protected transformation graph extension](transformation-graph.md) retains
an audio-less graph account and uses the existing revision index. A graph-only
revision auditum may have empty listening/decision arrays; it is restricted to
this artifact kind and does not imply a capture refusal or listening event.
Graph source evidence is immutable and each explicit patch parent advances by
exactly one revision. Real MASA validation is required on graph store writes.
