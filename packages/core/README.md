# @earworm/core

Canonical schemas and event-store primitives for Earworm.

`@earworm/core` exposes the schema-first protocol surface: session creation, append-only event stores, context queries, automation intent/rollback helpers, and export manifests.

```js
import { InMemoryEventStore, createSession, ingestPrompt } from "@earworm/core";

const session = createSession({ session_id: "sess_001", app_id: "demo", policy });
const store = new InMemoryEventStore(session);

ingestPrompt(store, {
  event_id: "evt_prompt_001",
  prompt: "close, breathy narration"
});
```

The JSON Schemas in `schemas/` are the public interchange contract. Fixtures in `fixtures/` are executable protocol examples.
