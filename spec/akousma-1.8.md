# Akousma specification 1.8 — spectral derivatives and native evidence

Status: opt-in contract. Package `akousma` 0.8.0 supplies the reader; existing
producer defaults remain unchanged until a host explicitly negotiates 1.8.0.
The 1.7.0 schema is frozen, including its exact `schema_version` constant.

`extensions["akouo.agent-native"]` carries `akouo/agent-native-evidence/v1`.
Earworm does not import AKOÚŌ. Hosts supply its offline structural and reference
validator; an unavailable validator means unvalidated evidence and refuses claim
admission. Unknown extensions on older records remain opaque and lossless.

`extensions["oida.spectral"]` carries `earworm/spectral-bundle/v1`. Source SHA-256,
excerpt SHA-256 and record ID are separate identities. The sampled representation
reference resolves against the host's listening-access declaration. Source sample
interval, effective rate, channel layout and analysis version remain explicit.
Each view retains its settings, axes, time origin, phase convention, reference
level, transforms and losses. A window names an exact coefficient recipe; a host
must retain its versioned implementation or explicit coefficients for replay.

Retained view objects are content-addressed. Host resolution binds SHA-256, dtype,
shape, encoded byte count and expanded byte count before download/allocation.
Numeric arrays must load with `allow_pickle=False`; object dtypes are prohibited.
Encoded objects are capped at 64 MiB and expanded arrays at 256 MiB; hosts may
impose tighter per-run totals. Shape multiplication must precede allocation.
Ephemeral/omitted views carry reasons and cannot expose downloadable object refs.

The `spectral` bundle evidence class identifies derivative evidence. PNG/SVG and
audified projections carry losses and a human target; they never replace native
evidence or establish physical support. Derivatives inherit the source audio's
retention, access and forgetting rules. This phase defines those obligations;
Akousmata lifecycle enforcement belongs to Phase 2.

New readers dispatch 1.7.0 and 1.8.0 explicitly. Producer/consumer delivery must
call version admission before serializing or persisting a new record. Never send
1.8.0 to an unadmitted reader, strip extensions, relabel it 1.7.0 or automatically
downgrade. Old readers may accept an unknown version via legacy fallback: their
acceptance is not evidence of negotiated support. Semantic checks reuse 1.7
invariants without changing the frozen artifact or caller record.

Not implemented here: spectral DSP, derivative storage/deletion, public download
routes or physical/model apparatus qualification. Host reference checks remain
mandatory even when the JSON structure validates.
