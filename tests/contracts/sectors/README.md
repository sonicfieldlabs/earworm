# Sector and scalar-comparison fixtures

The two MASA source records are synthetic variants of MASA 0.2.0's
`examples/0.2.0/valid/listening-analysis-audio.masa.json`, from source repository
HEAD `a967339d77cb7adfb977061e6f3299ff27e55619`. Their object identities are changed;
new centroid, energy, digital-level and duration values are explicit numeric
conformance vectors, not measurements of bundled audio or a physical apparatus.
Both sources pass the actual MASA validator. Original unknown extensions and
unavailable asset qualifications remain in the retained records.

Source license: MIT, copyright (c) 2026 Sonic Field Labs. The complete notice is
retained in `packages/core/fixtures/masa-source.LICENSE` and travels with the
packaged core fixtures. Earworm code and new contracts retain the repository's
MPL-2.0 license.

`comparison.json` defines two records, comparison options and the shared expected
relation. `cases.json` contains local-binding and scoped-comparison mutations.
`observation.json` reuses the D0e non-acoustic account with a sector/rendering;
`view.json` is the complete detached sector view. No rendering operation or DSP
engine was executed to construct these synthetic declarations.
