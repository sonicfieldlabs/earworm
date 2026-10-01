# Agent sectors and measurement descriptors — unreleased draft

`earworm/agent-sector/v1` groups evidence in the opt-in akousma 1.7 record through
`extensions.earworm_agent_sector`. Each entry references an attributable listening,
subject, existing access declaration, claim IDs and declared renderings. It keeps
acoustic signals, non-acoustic observations and structured reports distinct. Its
basis is a retained measurement, retained observation or interpretation; importing
a measurement does not make it the receiving agent's own sensing.

Rendering IDs resolve within that listening's existing context. Source, output,
transformation receipt, author, media type and access remain in one canonical
place. A sector cannot borrow a rendering or claim from another listening. A
rendering source must belong to the entry's subject, report or retained measurement.
A view does not execute a transformation, make private data public, or establish
human access. The existing rendering availability and access qualifications survive.

An acoustic measurement sector requires the declared effective representation and
analysis window to match its retained measurements. The existing access validator
checks bands, rates and channels. A numerical signal descriptor does not certify
physical capture or SPL. Non-acoustic observation entries require the explicit
observation-account binding and declared non-acoustic modality; they cannot be
relabeled as acoustic merely because a rendering or machine-readable report exists.

## MASA measurement mapping

`earworm/measurement-set/v1` preserves complete MASA source records once, and
references selected `masa:Measurement` objects through explicit descriptor mappings.
The importing host supplies MASA's validator; Earworm does not copy the foreign
schemas or infer a metric from a free-text name. Each mapping names an actor and
reason, a feature, its reference basis and a qualified band. Values, units,
representation, method/revision/parameters, uncertainty and window stay in the
retained measurement and are resolved for display or comparison.

The application-owned vocabulary accepts these exact unit/reference combinations:

| Feature | Source unit | Reference basis |
| --- | --- | --- |
| spectral_centroid | Hz | frequency |
| band_energy | sample^2 or sample^2*s | digital_energy |
| level | dBFS | digital_full_scale |
| level | LUFS | perceptual_loudness |
| level | dB_SPL | sound_pressure |
| duration | s | time |

No unit conversion is implicit. A LUFS descriptor remains a signal-derived quantity
and does not establish a human listener's loudness perception. Centroid and band energy require an explicit
increasing spectral band. Negative duration, centroid and energy values are
invalid; digital levels can be negative. A source Measurement must provide a
finite scalar and increasing temporal window in seconds. Other MASA value types
remain valid MASA data but are unsupported by this scalar mapping. Physical SPL
additionally needs method apparatus references, `parameters.calibration_ref` and
positive `parameters.reference_pressure_pa`; these are declarations whose truth
and external references the host must verify, not calibration performed here.

## Scalar comparison

`compareMeasurementDescriptors` / `compare_measurement_descriptors` produces a
`similar_by` relation using the existing criterion contract plus two explicit
record/descriptor references. Both records stay unchanged. It compares retained
scalar values only when feature, source metric, units, reference basis, band, temporal window,
method name, known method revision and parameters agree. Apparatus identities may
differ; physical comparability still requires host assessment. Incompatible or
unversioned descriptors are rejected rather than normalized silently.

The initial comparison method is `earworm:absolute-difference`, revision `1`:
`abs(left - right)`, in the original descriptor's unit, without normalization.
Lower values mean a smaller difference under this one criterion. This is not a
perceptual similarity score, a probability, an embedding metric or proof of a
common source. No DSP or measurement engine is implemented. Review starts
unreviewed, and the relation is an inference from retained values. Causal parents
and listening influence remain unchanged.

Reference validation resolves both descriptors and recomputes this method to
detect changed values, method, inputs or scores. Older arbitrary criteria without
descriptor references retain their existing behavior; the new comparison path
requires explicit negotiation. Unknown source extensions survive storage/reindexing.
In-place changes to the measurement set, sector or typed relation are protected;
use the existing explicit revision workflow. Foreign validation remains required
at ingress and before relying on imports from another writer. These checks do not
establish source truth, physical calibration, disclosure rights or user-interface
integration. No new term is promoted into the `masa:` namespace.


## APIs

The JavaScript SDK root exports `createMeasurementSet`, `measurementSetErrors`,
`agentSectorView` and `compareMeasurementDescriptors`. Python exports snake-case
equivalents from `akousma.agent_sectors`. Creation requires explicit supported
contracts and an injected MASA validator returning error strings. The detached
sector view is a local evidence view, not a public projection or a rendered UI.

`nextRecordErrors` / `next_record_errors` check local sector/mapping bindings;
`nextRecordReferenceErrors` / `next_record_reference_errors` additionally resolve
and recompute descriptor-backed comparisons. Existing store `get`, `reindex`,
`relation_details` and revision APIs are reused. Validation of the imported MASA
source's full policy/reference graph remains the injected validator's job.
See `tests/contracts/sectors/comparison.json` for the complete synthetic mapping,
comparison options and expected relation. The fixture numbers are declarations,
not newly calculated signal measurements.
