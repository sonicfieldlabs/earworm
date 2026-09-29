# Opt-in listening contracts

These additions are unreleased. They preserve akousma 1.6 and `earworm/auditum/v2`.
They do not imply that existing applications negotiate or enforce the new contract.

The [shared scenario matrix](../tests/contracts/scenarios/README.md) exercises
agent-only, independent human/agent, influenced ensemble, second-report,
beyond-band and generation-lineage accounts through the same JS/Python checks.

Akousma 1.8 adds `extensions["akouo.agent-native"]` and
`extensions["oida.spectral"]` behind explicit consumer admission. The frozen
0.7.0 Python reader was measured with an otherwise valid 1.7 record: it
round-tripped an unknown extension, but its broad fallback also accepted the
same record labelled 1.8.0. New producer and consumer boundaries therefore
check supported versions explicitly; old-reader rejection is not assumed.
Its portable fixture bundle ships under `@earworm/core/fixtures/scenarios/`.
Legacy envelope acceptance remains distinct from companion negotiation; the
matrix includes explicit old-reader rejection for 1.7 records.

## Four independent declarations

The canonical [listening-access schema](../packages/core/schemas/listening-access.schema.json)
identifies `earworm/listening-access/v1`. Store a declaration in
`extensions.earworm_listening_access`; its `declaration_id` can be the target of an
existing listening's `apparatus_ref`. Resolve `subject_ref` and evidence references
within the consuming application's explicit reference scope.

| Declaration | What it describes | What it does not establish |
| --- | --- | --- |
| `capture` | Physical apparatus and supported frequency band, with evidence references | That a source emitted energy throughout that band or that the captured event was detected |
| `sampled_representation` | A particular representation's sample rate and retained band | The physical capture range or a model's effective input |
| `model_input` | Actual input representation, effective band, window, preprocessing receipts, and model reference | Native understanding of every represented component |
| `human_access` | Per-listener access modes, chain, conditions, rendering references, and supporting declarations | That anyone actually perceived or understood the signal |

`known` means a concrete declaration with evidence references. Consumers still
need to resolve and assess that evidence. Other states are `unknown`, `withheld`,
`unavailable`, and `not_applicable`, each with a reason. Missing evidence must not
be replaced with a sample-rate-derived physical bandwidth. A visual or textual
rendering is not an acoustic access claim. An empty rendering list does not prove
that perceptual access was impossible.

The validators enforce ordered bands, each digital representation's own Nyquist
limit, and a nonempty model input window. They do not compare physical frequencies
across a frequency translation without a transformation receipt. Nyquist bounds
possible representation; it does not guarantee retained energy or detector support.
Subsample timing is a numerical estimate, not evidence of extra physical sensing.

```js
import { LISTENING_ACCESS_CONTRACT, assertSupportedContracts, listeningAccessErrors } from "@earworm/sdk-js";
assertSupportedContracts([LISTENING_ACCESS_CONTRACT], supportedContracts);
const errors = listeningAccessErrors(record.extensions.earworm_listening_access);
if (errors.length) throw new Error(errors.join("; "));
```

```python
from akousma.listening_contracts import (
    LISTENING_ACCESS_CONTRACT, assert_supported_contracts, listening_access_errors,
)
assert_supported_contracts([LISTENING_ACCESS_CONTRACT], supported_contracts)
errors = listening_access_errors(record["extensions"]["earworm_listening_access"])
if errors:
    raise ValueError("; ".join(errors))
```

The required-contract list belongs to the producer/consumer exchange. Call the
negotiation helper before making a decision that depends on these declarations.
It deliberately has no implicit supported-contract default. Legacy readers may
retain the extension opaquely, but successful legacy akousma validation does not
mean the new declarations were checked. JSON Schema checks shape; the SDK helpers
also enforce numeric relations. Neither resolves external references or fetches
network resources.

## Explicit pass adapter

`adaptListeningPasses` in JavaScript and `adapt_listening_passes` in Python accept
validated AKOÚŌ `passes`, `participants`, an explicit `bindings` array, and an
optional `ensemble`. Each binding provides `pass_id`, `listening_id`,
`report_namespace`, and `contract`. Every pass must have exactly one unique stored
listening ID. Missing references, self-influence, inconsistent influence edges,
and permission/disagreement loss in a swarm are rejected.

The adapter validates the produced Earworm listening and ensemble structures. It
is a transport adapter, not a replacement for AKOÚŌ's source schema and semantic
validation. The output contains `listenings`, `ensemble`, `pass_to_listening`, and
an independent `source` snapshot. Retain the latter two under an application-owned
extension such as `extensions.akouo_pass_adapter`; they preserve participant IDs,
source references, claims, moment, revisions, reorientation, and other source
fields that have no direct auditum/v2 slot. A null ensemble should be omitted from
an auditum object, whose optional `ensemble` field accepts only an object.

The adapter never infers influence from ordering or co-membership. Matching
attributions establish structural consistency, not proof that influence occurred.
Revisions and new reports belong in new records; this adapter does not rewrite a
stored record or grant action authority. The Python store validates declarations
in `extensions.earworm_listening_access` and protects that key and
`extensions.akouo_pass_adapter` from in-place addition, replacement, or deletion
on an existing record. Changing them requires a fresh record and revision link.
Other extension metadata keeps its existing curatorial behavior.

## Checks

`pnpm check` covers JavaScript and canonical schema fixtures. Install the Python
package with Python 3.10+ using `pip install './packages/py-akousma[dev]'` and run
`python3 -I scripts/check_python.py --junitxml /tmp/earworm-python.xml`. Both suites use the
same access cases and expected adapter output under `tests/contracts/`.
`node scripts/sync-akousma-schema.mjs` refreshes the bundled Python schemas; a
regression check prevents schema drift.

## Subjects, recipients, renderings and claim lifetime

The opt-in [listening-context schema](../packages/core/schemas/listening-context.schema.json)
identifies `earworm/listening-context/v1`. Store it in
`extensions.earworm_listening_context` and negotiate it before relying on its
fields. Each context binds one existing `auditum.listenings[].listening_id` to a
subject reference, addressed recipients using the complete listener taxonomy, a
report reference/contract/format, and an access declaration. The contexts cover
every listening in that record exactly once. A context can bind the primary
`extensions.earworm_listening_access` declaration or an additional declaration in
its `access_declarations` array. IDs must be unique across both locations. Each
listening resolves its own subject and apparatus; an ensemble must not borrow one
model's input limits for another model or another listening subject.

Use `listeningContextErrors(context, record)` or
`akousma.listening_context.listening_context_errors(context, record)` to check
record-local links. These helpers check listening identities, report contract,
subject/access binding, recipients, rendering references, and claim ownership.
The host still resolves external report bodies, subjects, evidence, policy, author,
and transformation references within an authorized scope. Matching identifiers
alone do not prove those external objects exist or that a report is correct.

Three declarations remain independent:

- `report.readability` describes structured encoding or human-readable content.
- `report.human_rendering` states whether an identified human rendering is
  available, absent (`none`), unknown, withheld, or unavailable.
- The referenced access declaration describes a human listener's actual declared
  chain, conditions, and access modes. Neither of the first two implies hearing.

A rendering identifies its source, distinct output, transformation receipt,
author, media type, and access qualification. An interpretation of a structured
report has `kind: "interpretation"` and its own output and author; it does not
replace the report. Declaring a rendering available requires references to
renderings in that same context. A private or restricted rendering is not thereby
unreadable, and `none` does not establish that human perception is impossible.
The agent-sector contract now resolves rendering metadata within each listening;
application render execution remains downstream.

Each claim reference has separate `validity` and `retention` declarations:

| Declaration | Meaning |
| --- | --- |
| Validity `expires` | Declared currency from `issued_at` up to, but excluding, `expires_at` |
| Validity `no_expiry` | An explicit, reasoned absence of an expiry rule; factual truth still needs assessment |
| Validity `unknown` | Currency cannot be inferred |
| Retention `review_after` | Time to review the referenced retention policy; no automatic deletion |
| Retention `policy` or `unknown` | A host policy decision is required |

`claimValidityAt(claim, now)` / `claim_validity_at(claim, now)` return `current`,
`expired`, `not_yet_valid`, or `unknown`. `claimRetentionAt` /
`claim_retention_at` return `review_due`, `review_not_due`, or `policy_required`.
Timestamps use UTC `YYYY-MM-DDTHH:mm:ss[.SSS]Z` with valid calendar dates and years
1000–9999; the explicit evaluation time makes both SDKs deterministic.

Claim expiry does not change `actions[].authority.expires_at`, grant execution,
or delete evidence. A claim can be expired while its record remains retained.
Use the existing retention decision and `forget_with_receipt` / `forget` workflow
when an authorized policy actually calls for forgetting. A content-free receipt
may survive; it does not restore the claim or make a missing reference available.
These helpers neither schedule policy work nor resolve permissions for the host.

The Python store validates and protects `extensions.earworm_listening_context`,
including against removal. Curatorial edits to other extensions remain supported.
Changes to a stored context require a new record and revision link. Plain legacy
record validation and opaque JSON round trips do not negotiate this contract.

### Completing the unreleased apparatus draft

Known sampled and model-input declarations now require explicit `channels`.
Known model inputs also require `blind_spots`, with an empty list meaning none
are declared, not independently proven absence of limitations. Hosts must not
infer channels from a model name or invent an empty limitations list. When the
required information is unknown, keep the declaration qualified unknown and
retain the source evidence separately. Revalidate earlier unreleased draft
fixtures before integration; released akousma and auditum formats are unchanged.

## Opt-in record evolution

The unreleased [1.7/v3 draft](../spec/akousma-1.7-draft.md) adds canonical appeals,
versioned relations, research proposals and generation decisions. It uses a
separate generated schema; 1.6 constructors and the released schema stay intact.
Both SDKs expose explicit validation and appeal-promotion APIs, and the Python
store retains full relation metadata alongside its existing coarse edge index.

The unreleased [observation-account binding and matter context](../spec/observation-accounts.md) retain
MASA/AKOÚŌ source attribution, register/scale labels and non-acoustic distinctions.
JavaScript and Python APIs reuse injected foreign validators; local store writes
protect the retained mapping and independent context declarations.

The unreleased [agent sectors and measurement descriptors](../spec/agent-sectors.md) reuse existing
rendering metadata and MASA source records. A conservative scalar comparison
checks compatible methods/units/windows; it performs no DSP or perceptual scoring.


## Local views and transformation graphs (unreleased)

The [auditum view](../spec/auditum-view.md) checks explicit host permission
before record or receipt lookups. It distinguishes forgotten, unavailable and
withheld references, and excludes free-text receipt fields from the projection.
The Python store exposes `auditum_view`; the JavaScript SDK exports `auditumView`.

The [transformation graph](../spec/transformation-graph.md) retains one MASA
source record and maps representations to explicit patch nodes with directed,
receipt-backed edges. Both SDKs require the host's actual MASA validator and
versioned direction registry. Graph accounts now use protected storage and explicit patch revisions. Typed
transposition receipts preserve separate rate/duration/band/hash declarations;
external engine execution remains downstream.
