# Conformance Tests

Conformance tests will verify whether an application or adapter produces Earworm-compatible objects.

Current checks live in local scripts:

- `scripts/validate-fixtures.mjs`
- `scripts/test-event-store.mjs`
- `scripts/conformance.mjs`

Reusable accept/reject vectors live in `tests/conformance/vectors`. External implementations can replay those JSON files to verify append validation behavior without depending on Sonic Field Labs applications.

`tests/fixtures/germ-organism-mapping.session.json` is the first cross-stack fixture: a germ organism metadata chain represented as Earworm events for prompt, generation, analysis, harvest, provenance, and lineage.
