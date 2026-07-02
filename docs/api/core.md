# Core API

The first implementation surface lives in `@earworm/core`.

## Session and Store

```js
import { createSession, InMemoryEventStore } from "@earworm/core";

const session = createSession({
  session_id: "sess_001",
  app_id: "my-app",
  policy
});

const store = new InMemoryEventStore(session);
```

## Capture Helpers

All specialized helpers append validated event-shaped records to the event store:

- `ingestPrompt`
- `ingestGenerationRequest`
- `ingestGeneratedAsset`
- `ingestAlignment`
- `ingestAnalysis`
- `emitModulationIntent`
- `commitAutomation`
- `revertAutomation`
- `recordAgentAction`
- `createSnapshot`

The design rule is that helpers are convenience APIs. The event log remains the canonical history.

## Query and Export

- `queryContext(session, events, selector)` returns scoped context bundles for agents or processors.
- `exportManifest(session, events, scope)` returns a portable audit object for assets, events, provenance, policy, and reconstructed state.
- `JsonlEventStore.appendAndPersist(event)` validates one event, appends it in memory, then atomically persists the full hash-chained JSONL log.
- `restoreSnapshot(session, events, snapshotEventId)` rebuilds a session state up to a recorded snapshot event.
- `byTextRange(start, end)` returns events whose character or word ranges overlap the requested interval.
- `createBreathAutomationFromContext(bundle)` is the first reference rule mapper for prompt/alignment-driven breath automation.

Asset-scoped selectors include causal parent events so an exported or queried asset can carry its prompt, proposal, and generation lineage even when those parent records do not contain an `asset_id` directly. Use `event_types` and `include` to limit the direct asset matches; parent lineage remains included for auditability.

## Local Verification

```sh
pnpm validate
pnpm test
pnpm check
```

## Manifest Fixture Export

```sh
pnpm manifest:fixture
pnpm manifest:validate
```

This writes `tests/fixtures/aum-voice-generation.export-manifest.json` from the AUM-style session fixture.

## JavaScript SDK

`@earworm/sdk-js` provides a thin `EarwormClient` wrapper around the core event store. It is intended for application developers who want the MVP method names without managing store helper calls manually.
