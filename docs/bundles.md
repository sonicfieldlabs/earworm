# E17 bundle manifests (unreleased)

`earworm/listening-memories/v1` and `earworm/agent-sounds/v1` are opt-in manifests.
Python exposes `akousma.bundles.bundle_manifest_errors`; JavaScript exposes
`bundleManifestErrors` from the existing SDK. Canonical schema:
`packages/core/schemas/bundle-manifest.schema.json`, synchronized into the Python
wheel by the existing schema script.

Entries name identity, path, serialized payload SHA-256, canonical source SHA-256,
schema version, evidence class, covenants, transforms and recipient requirements.
Paths are bounded records/assets members and IDs/paths are unique. Public
manifests allow only metadata projections. Agent-sound manifests require audio
and declared recipient capabilities. Representation metadata keeps encoding,
sample rate and sampled-band qualification separate from human perceptual access.
A Nyquist limit, recipient choice or digital level is not an inaudibility claim.
Human rendering availability remains a separate declaration.

Hosts verify bytes and actual provenance. Manifest validity is not permission,
current disclosure, a listening pass, or successful execution. Akousmata owns
canonical record export/import and current revocations; GERM supplies generated
assets. Projections cannot be promoted into canonical records. Unknown private
extensions stay in private record payloads, never implicitly in public metadata.
The shared `akousma.masa_runtime` adapters invoke owner-selected installed MASA
modules offline; incoming bundles cannot choose executable validators.

The shared synthetic manifest exercises Python/JS acceptance and negative cases.
Akousmata integration additionally tests exact JSON preservation, old/new reader
negotiation, current forgetting and actual MASA graph validation. No release
numbers change and no broader runtime/device conformance is implied.
