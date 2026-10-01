# Synthetic receipt recipe vectors

`sources.json` contains four alternative, synthetic metadata scenarios: filtered
sample-rate conversion, playback-rate change, frequency translation and pitch
shifting. Their source records derive from MASA's MIT-licensed processing example;
see [provenance and license](../graphs/README.md). No DSP ran and no audio is
bundled. Unknown integrity states stay unknown; a syntactically valid declared
hash is not proof that bytes were verified.

`cases.json` is shared by JavaScript and Python. It includes mismatched rates,
ratios, duration, bands, algorithms, hashes, channels, operation types, policy and
completion status. Unit tests stub foreign validation explicitly; the installed
and packed integration tests invoke the actual MASA validator and registry.
`graphs/records.json` separately exercises source-preserving artifact/revision
parity and the existing store revision index.
