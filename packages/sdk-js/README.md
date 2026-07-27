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

Akousma v1.5 helpers make accountable hearings and pre-capture decisions addressable while keeping
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
