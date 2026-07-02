# AUM Lite Demo

This example will become the minimal AUM-style vertical slice:

1. Create a session.
2. Ingest a voice prompt.
3. Record a TTS generation request.
4. Attach a generated audio asset.
5. Ingest alignment and analysis frames.
6. Query context for the generated line.
7. Commit breath automation.
8. Export an audit manifest.

The current fixture for this flow is `packages/core/fixtures/aum-voice-generation.session.json`.

Run:

```sh
pnpm example:aum
```
