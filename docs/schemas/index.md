# Schemas

Earworm uses JSON Schema as the canonical protocol contract.

Current schema drafts:

- `EarwormSession`
- `EarwormEvent`
- `AssetRef`
- `RetentionPolicy`
- `ProvenanceRecord`
- `SignalPacket`
- `AnalysisFrame`
- `FeatureStreamRef`
- `ModulationIntent`
- `AutomationLane`
- `ContextSelector`
- `ContextBundle`
- `ExportManifest`
- `Akousma` spec v1.5, including current `earworm/auditum/v2` route decisions and legacy `earworm/auditum/v1` compatibility
- `Earworm Forgetting Receipt` v1, the content-free durable receipt for a completed forget operation

Fixtures are executable examples of the protocol. Run `pnpm validate` to validate the current fixture set against the schemas.

## Stability

The current schemas are MVP drafts. Breaking changes are allowed until M0 is formally locked, but changes should update fixtures and tests in the same commit.
