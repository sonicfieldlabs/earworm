# Permission-aware auditum views — unreleased draft

`earworm/auditum-view/v1` is a detached local view of an existing auditum and its
one-hop record references. It reuses `earworm/forgetting-receipt/v1`, the Python
store's `get` and `forgotten` reads, and the existing forgetting path. It does not
forget records, restore audio, edit evidence, or authorize disclosure.

The host must negotiate both contracts and provide a synchronous permission
callback. Permission is checked before looking up either a record or its receipt,
including the requested root. Only a boolean result is accepted. Denied access
returns `withheld` without revealing whether the ID exists. Resolver errors
propagate; a storage failure must not become an assertion of absence. Host
resolvers return `null` in JavaScript or `None` in Python for missing values.

| State | Meaning within the host-authorized local store |
| --- | --- |
| `available` | The record exists and its identity and record structure validate. This says nothing about audio availability. |
| `forgotten` | The record is absent and a valid receipt for exactly that ID exists. |
| `unavailable` | Neither the record nor a forgetting receipt was found. The reason is unknown. |
| `withheld` | The host denied lookup. Existence and receipt status are undisclosed. |

An available root includes its detached `auditum` (or `null` for a legacy record
without one) and a sorted, deduplicated reference list. References include causal
parents, relation targets, the revised record, retained appeal source, generation
and subsequent-listening record IDs, and descriptor-comparison record IDs. The
root's own ID is excluded. Asset IDs, report/listening IDs and foreign MASA IDs
are not interpreted as Earworm store IDs. Traversal stops after one hop. Additional
application-specific references require a separately negotiated resolver.

Only an available root includes its auditum. Referenced available records expose
availability only; they do not recursively disclose their content. A missing or
forgotten target does not invalidate or rewrite the surviving root. Its relation
and other retained evidence remain attributable. A new view can reflect changed
permissions or storage state without changing either record.

## Receipt projection

The canonical [view schema](../packages/core/schemas/auditum-view.schema.json)
allows only receipt contract, receipt ID, record ID, creation time, record-deleted
flag, audio-deletion-requested flag, audio-deleted flag and shared-audio-preserved
flag. The projection rejects mismatched identities, unsupported contracts, invalid
UTC timestamps, non-boolean flags and contradictory audio outcomes.

Arbitrary actor, reason, recovery text and unknown receipt fields are omitted.
Identifiers and timestamps remain metadata; the host must still authorize their
disclosure. This projection does not change the original local receipt. Callers
of the older raw receipt APIs must continue to handle their free text as private.

The audio flags report the outcome at forgetting time. A shared object may have
been deleted later; its historical preservation is not a promise of present
availability. An unrequested audio deletion does not imply audio was erased.
Receipts make no claim about remote copies, backups, independently retained
records or source snapshots in surviving accounts. They must not be used to
reconstruct forgotten content. Existing explicit forgetting rules and shared
content-addressed audio handling remain authoritative.

## Use

```python
from akousma.auditum_view import AUDITUM_VIEW_CONTRACT, FORGETTING_RECEIPT_CONTRACT

view = store.auditum_view(
    record_id,
    can_read=lambda identifier: identifier in host_authorized_record_ids,
    supported_contracts=[AUDITUM_VIEW_CONTRACT, FORGETTING_RECEIPT_CONTRACT],
)
```

JavaScript exports `auditumView`, with `readRecord`, `readReceipt`, `canRead` and
`supported_contracts` options. Python also provides the resolver-based
`akousma.auditum_view.auditum_view`. Hosts with asynchronous storage must resolve
a permitted snapshot before calling this synchronous API; a Promise is not a
permission decision. Neither SDK performs remote dereferencing or supplies a
public projection of the root auditum. Application screens remain downstream.
