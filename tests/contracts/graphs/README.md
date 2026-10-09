# Transformation graph fixtures

`processing.json` retains the MASA 0.2.0 valid processing example and a snapshot of
its versioned lineage direction registry, with an explicit application patch
mapping and expected directed edge. These are synthetic declarations; source
bytes are unavailable and hashes remain qualified unknown. No engine ran.

MASA-origin source and registry material is MIT-licensed, copyright 2026 Sonic
Field Labs; see [license](../../../packages/core/fixtures/masa-source.LICENSE).
The source is from `examples/0.2.0/valid/processing.masa.json` and registry from
`ontology/0.2.0/relations.json` in MASA. The registry snapshot is test data only;
runtime code requires the host's actual versioned MASA registry and validator.
`cases.json` mutates graph structure and bindings. Both SDK suites consume the
same vectors; real foreign validation belongs to the installed integration smoke.
