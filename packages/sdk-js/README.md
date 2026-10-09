# @earworm/sdk-js

Developer-facing JavaScript SDK for Earworm.

The SDK is intentionally thin. It wraps `@earworm/core` with a client object that exposes the MVP method names from the development plan while keeping the event log as the canonical state.

```js
import { EarwormClient } from "@earworm/sdk-js";

const client = EarwormClient.create({
  session_id: "sess_001",
  app_id: "demo",
  policy
});

client.ingestPrompt({
  event_id: "evt_prompt_001",
  prompt: "tired detective, close and breathy"
});
```

Akousma v1.6 helpers make accountable hearings, listening-only accounts, and pre-capture decisions addressable while keeping
producer reports namespaced:

```js
import { createAkousma, createAuditum, createRouteDecision } from "@earworm/sdk-js";

const record = createAkousma({
  audio: { asset_id: "asset_1" },
  originatingApp: "oida",
  auditum: createAuditum({
    listenings: [{
      listening_id: "lst_1",
      listener_id: "oida",
      listener_type: "agent",
      created_at: new Date().toISOString(),
      report_namespace: "oida.signal",
      contract: "akouo/v0.9"
    }],
    routeDecisions: [createRouteDecision({
      decisionId: "decision-listen-1",
      gate: "inference",
      outcome: "proceed",
      subject: "accountable listening pass",
      reason: "The user requested an observe-only pass.",
      actor: "oida-router",
      listeningId: "lst_1",
      producerContract: "akouo/v0.9"
    })]
  })
});
```

Each listening stays attributable. Disagreement, absence, action authority,
receipts, and revision are recorded rather than flattened into a consensus.
Use `listenerTypes(record)` for the lossless canonical listener facets,
`recordClass(record)` for the coarse navigation class, and
`revisionOf(record)` for the direct revision target. The class never relabels
community, institutional, sensor, habitat, other-animal, ensemble, or other
listening as human or agent.

Unreleased opt-in [listening contracts](../../docs/listening-contracts.md) add
qualified access declarations and explicit AKOÚŌ pass-to-listening adaptation.

The opt-in [1.7/v3 draft](../../spec/akousma-1.7-draft.md) adds `nextRecordErrors`,
`nextRecordReferenceErrors`, and `promoteLegacyAppeal`. Default constructors
remain 1.6 and consumers must explicitly negotiate the draft contracts.

The unreleased [observation-account binding and matter context](../../spec/observation-accounts.md) retain
MASA/AKOÚŌ source attribution, register/scale labels and non-acoustic distinctions.
JavaScript and Python APIs reuse injected foreign validators; local store writes
protect the retained mapping and independent context declarations.

The unreleased [agent sectors and measurement descriptors](../../spec/agent-sectors.md) reuse existing
rendering metadata and MASA source records. A conservative scalar comparison
checks compatible methods/units/windows; it performs no DSP or perceptual scoring.


## Local views and transformation graphs (unreleased)

The [auditum view](../../spec/auditum-view.md) checks explicit host permission
before record or receipt lookups. It distinguishes forgotten, unavailable and
withheld references, and excludes free-text receipt fields from the projection.
The Python store exposes `auditum_view`; the JavaScript SDK exports `auditumView`.

The [transformation graph](../../spec/transformation-graph.md) retains one MASA
source record and maps representations to explicit patch nodes with directed,
receipt-backed edges. Both SDKs require the host's actual MASA validator and
versioned direction registry. Graph accounts now use protected storage and explicit patch revisions. Typed
transposition receipts preserve separate rate/duration/band/hash declarations;
external engine execution remains downstream.
