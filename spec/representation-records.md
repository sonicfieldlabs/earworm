# Representation records

Opt-in source candidate: JavaScript packages 0.8.0, Python `akousma` 0.9.0,
Akousma 1.9.0. Existing constructors keep their 1.6 defaults. Canonical schemas
live in `packages/core/schemas/`; byte-identical Python copies live in
`packages/py-akousma/akousma/`.

## Permitted navigation

Owner lists retain their existing response contract and add `next_cursor`, an
opaque continuation token or null. A page contains at most the requested 1–200
permitted records and scans at most 512 indexed candidates. An empty page can
still have a continuation; clients keep following it to reach older material.
No hidden identity, position or total is encoded in the public token or response.
Cursor state lives in a separate navigation table, expires after 15 minutes,
and binds the owner, audience and exact filters. Expired or mismatched tokens
are refused. Refresh starts from the newest records.

Ordering is descending creation time, then record identity. Keyset continuation
survives removal of the boundary record and excludes newer insertions ahead of
that boundary. Each page resolves current metadata permissions for every
candidate; Station also checks current local disclosure before including it.
Filters select representation form, output kind and a case-insensitive literal
search of permitted record metadata. Search does not read artifact bytes.
Navigation does not change retained record or artifact schemas.

## Material and its uses

A representation identifies material through its form, origin, source class,
terms, artifact identity, preservation, convention, and time basis. A text can
originate as correspondence or a written work. A recording can reach a process
through a transcript. Generated audio has real bytes while its origin may
have no acoustic capture. These properties stay independent.

| Contract | Required meaning |
| --- | --- |
| `earworm/representation/v1` | Material identity, exact bytes, encoding where textual, origin, terms, convention, and time basis |
| `earworm/representation-access/v1` | Operation role and actual supplied material, with explicit coverage |
| `earworm/representation-output/v1` | Account, work, prompt, or event log with identity, completion, authors, and input accesses |
| `earworm/representation-record/v1` | Declared scope connecting material, accesses, outputs, source relations, outcomes, and bindings |
| `earworm/representation-measurement/v1` | Separately supplied method result tied to one representation |
| `earworm/akousma/v1.9` | Opt-in memory envelope preserving source provenance and lineage |

Roles belong to an operation. Subject, score, and work can identify its primary
input. Account and context preserve different uses of material. Instruction
requires a separate document binding. Reading a file named LISTENING.md as a
subject does not activate it as instructions.

## Original bytes and supplied context

A retained artifact names its SHA-256, byte count, and reference. Inline text
is an optional complete UTF-8 representation; validation recomputes its digest
and byte count without changing whitespace or line breaks. Character count
and byte count differ, including in the shared Unicode fixture. Other encodings
can be declared for a host adapter, while inline text uses UTF-8.

Available access identifies exact received-byte identity. Full access names
the original and cannot omit or abbreviate it. Partial access names a distinct
derivative, explicit ranges, and a transformation with method and losses.
The original remains independently identified. There is no 4,000-character
document cap in these contracts. Host context limits use explicit partial
access and keep the full document identity.

Terms identify applicable material-specific conditions, or explicitly record
that they are unknown. The executing owner must resolve and enforce those terms
at the relevant operation. Schema and byte validation grant no retention,
disclosure, training, publication, or action permission.

Time bases distinguish sequence, authored time, reported event time, capture,
execution, and unknown. Event times require a clock reference. Extents have
ordered bounds and units. A textual gap has no implied frequency or duration.
A convention identifies an interpretation and revision; unknown interpretation
stays explicit for capability routing.

## Completed works and returns

A complete output points to a retained complete artifact with a fresh identity.
A work has a `response_to` relation; an account has an `account_of` relation.
A prompt keeps its own output kind. The resulting work can remain written and
become another primary input. No descendant corroborates its parent claim.

The optional return block names a previous operation and distinguishes the
original subject from its descendant. Context basis is independent, informed,
shared analysis, or unknown. Informed and shared returns name actual context
accesses. Independent context cannot carry a prior account. An owner resolver
confirms the previous subject or output identity before admission. This
declaration concerns supplied context, not independence from shared training.

| Outcome | Meaning |
| --- | --- |
| `pending` | Material may be supplied; no output declared |
| `completed` | Complete outputs retained |
| `no_response` | Attributed report of supplied material and no subsequent response |
| `refused` | Stop before material was supplied |
| `withheld` | Explicit withholding outcome |
| `failed` | Explicit failure, possibly retaining a partial output |
| `missing` | Missing history without a supply claim |
| `source_only` | Material described independently of an operation's listening |

Supply cannot prove inward attention. A null is an attributed report, while
missing history preserves the record's uncertainty. Both remain available for
another participant's account.

## Document and binding references

Binding references reserve separate identities for the complete document
digest, adoption, application, operational scope, and effective time. An
instruction access names its binding, and invocation scope must match the
operation. Byte admission requires the owner's binding validator. A declared
binding with no owner validation remains unadmitted.

The next phase implements scope hierarchy, commitments, controls, replacement,
and revocation. Supplying references does not adopt a file or enforce its prose.
Unknown terms and unimplemented controls must remain explicit.

## APIs and validation layers

Python exposes `representation_errors`, `representation_record_errors`,
`representation_measurement_errors`, `record_19_errors`, and
`admit_representation_record` in `akousma.representations`. JavaScript exports
their camelCase counterparts through `@earworm/sdk-js`. Both the SDK and core
export TypeScript representation types.

Shape and semantic checks validate identities, roles, references, coverage,
outcomes, and acyclic causal lineage. Byte admission additionally checks actual
content from inline material or a host resolver. Instructions and returns need
owner callbacks. No URL is fetched, and the result is a detached copy. These
checks do not certify a transformation algorithm's correctness or prose truth.

The repository's synthetic work can be checked directly:

```python
import json
from pathlib import Path
from akousma.representations import REPRESENTATION_CONTRACTS, admit_representation_record

example = json.loads(Path("tests/contracts/representations/work.json").read_text())
admitted = admit_representation_record(example, supported_contracts=REPRESENTATION_CONTRACTS)
assert admitted["outputs"][0]["kind"] == "work"
assert admitted["outputs"][0]["completion"] == "complete"
```

The fixture includes no audio asset or model invocation. It exercises the
contract; a Khipu runtime demonstration belongs to subsequent integration.

## Compatibility and migration

The generated 1.9 schema extends the unchanged 1.8 source with an explicit
representation-record branch. A legacy-shaped audio record deliberately
labelled 1.9 still receives the existing 1.8 semantic checks. A representation
record cannot impersonate the legacy audio/auditum path.

Existing records remain at their original versions. Consumers must negotiate
support or preserve a new record opaquely under their importer rules. They must
not strip its extension, fabricate audio, or relabel it as 1.8. The migration
path creates a new record or revision with source references; no in-place
migration is provided.

The current Python store explicitly refuses 1.9 persistence. Representation
custody, queries, policy enforcement, and projection require the later owner
adapter. This guard keeps schema support from silently activating an
audio-oriented store path. Oída, Akousmata, Khipu, and installer consumers are
not activated by this source candidate.
