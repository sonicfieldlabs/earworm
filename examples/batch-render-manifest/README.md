# Batch Render Manifest

This example will demonstrate Earworm as a sidecar format for batch-generated media.

The target flow is:

1. Load or create a session.
2. Append generation and render events.
3. Validate provenance completeness.
4. Export an `ExportManifest`.
5. Validate the manifest in CI.

Current command:

```sh
pnpm manifest:fixture
pnpm example:batch
```
