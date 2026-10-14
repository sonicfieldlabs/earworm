# Representation custody

Akousma 0.10.1 adds `RepresentationStore` and
`MaterialTerms` beside the existing shared-store interfaces. The adapter
explicitly admits the Phase 3 Akousma 1.9 family. Default `AkousmataStore.put`
continues to refuse it without a representation-aware owner adapter. Existing
audio constructors and record contracts keep their behavior.

`RepresentationStore` negotiates the required contracts, verifies exact retained
bytes and immutable identities, validates instruction bindings and return
history, and rechecks current owner uses before and inside admission. Artifact
blobs, representation metadata, operation identity, record membership, canonical
record and memory lineage commit in one SQLite transaction. Inline text is
removed from retained metadata. No second memory archive is introduced.

`MaterialTerms` stores explicit owner declarations in the same database. Each
declaration has an actor, basis, action set, revision and optional UTC expiry.
Updates require the expected revision. Revocation, expiry, missing parents and
cycles close access. A generated or transformed representation inherits the
current restrictions of every input, even when those inputs live in an earlier
record. A different declared terms reference cannot remove inherited conditions.
The declaration is operational permission, without a verified license or legal
agreement claim.

Read, metadata access, execution, retention, local/external disclosure,
owner/public export and forgetting have separate actions. Every artifact and
query uses the current terms. `producers` links a reused output to its existing
memory record. `operation` resolves an original or descendant return against
the retained previous operation and its actual outputs. Retention keeps that
previous memory as a parent.

Records, operation identities and representation metadata cannot be overwritten
or silently reused. Repeating the same live record is idempotent after admission.
Content-addressed objects are checked against their digest and size on reading.
Corruption or an identity alias fails; it does not become a new revision.

`forget` creates the existing content-free durable receipt and logically removes
unshared representation artifacts. Shared material remains available only through
another live canonical record. Identity tombstones prevent silent resurrection.
Even the legacy forget operation makes orphan artifacts unavailable. This is
logical availability and cleanup; it does not establish physical erasure of
SQLite pages, backups or copies already disclosed.

Schemas and JavaScript contract fixtures remain the Phase 3 definitions. The
new Python owner adapter changes persistence under those existing contracts.
The [representation specification](../spec/representation-records.md) defines
their meaning. Oída and Akousmata must use the matching candidate
wheels before enabling this opt-in path.
