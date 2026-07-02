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
