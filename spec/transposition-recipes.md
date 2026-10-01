# Transposition receipt recipes — unreleased draft

`earworm/transposition-recipe/v1` is an application annotation in a MASA operation
receipt's `extensions["earworm:transposition"]`. It classifies a declared completed
unary transformation and binds its source/output bands and affected input window.
It is not an executable request and grants no authority. MASA validates the source
record, policy and lineage; Earworm checks the additional application semantics.

| Recipe kind | Receipt operation | Required parameters and behavior |
| --- | --- | --- |
| `filtered_resample` | `earworm:resample` | Versioned filter algorithm; new representation rate; selected duration preserved; output band is a subset of the input band and fits the output Nyquist limit. |
| `playback_rate` | `earworm:playback_rate` | Positive `rate_ratio`; output rate equals input rate times ratio; duration is divided by ratio and frequencies multiplied by ratio. This changes sample interpretation, not filtered resampling. |
| `frequency_translation` | `earworm:frequency_translate` | Finite `offset_hz`; output band endpoints equal input endpoints plus the offset. Duration is preserved. A band crossing zero or Nyquist is rejected; folding/conjugation requires another explicit recipe. |
| `pitch_shift` | `matter.pitchshift` | Reuse `parameters.cents`. Band frequencies scale by `2 ** (cents / 1200)`. `duration_behavior` explicitly declares preserved or changed duration; neither is inferred from the operation name. |

The recipe carries `algorithm.name`, `algorithm.version`, `input_window_s`,
`input_band_hz`, `output_band_hz` and `duration_behavior`. Rates, channel counts,
actual durations and integrity stay in the existing input/output Representations;
engine identity/version and typed operation parameters stay in the receipt.
Only completed, permitted, one-input/one-output receipts can claim this recipe.
A named engine and algorithm version are required. Failed/refused operations use
normal MASA non-action receipts and must not carry a completed-output recipe.

Known positive sample rates, durations and channel counts are required. Channels
are preserved by these four recipes. The input window must be increasing and
inside the source duration; output duration is compared with the selected window,
not automatically with the full source. Numeric equalities use a fixed relative
and absolute tolerance of 1e-9 for representation rounding, not a perceptual or
physical error budget. Both bands must be increasing, nonnegative and within
the respective sampled Nyquist limits. Filtering is declared by the algorithm;
metadata validation does not measure stop-band rejection or establish alias-free
processing. Playback-rate ratios preserve the declared sample count relationship.

Representation `integrity` remains qualified. A known hash for this application
uses `value.sha256` with 64 hexadecimal digits. Unknown, unavailable, withheld and
deleted integrity retain MASA's qualified reasons/references; none becomes a
verified digest. The validator never fetches bytes or calculates a digest from
metadata. Host byte verification and DSP evaluation remain separate evidence.

Application-specific operations stay in `earworm:`. Pitch shifting retains MASA's
existing operation; frequency translation is never relabeled as pitch shifting.
The annotations do not establish capture bandwidth, effective model input or
human perceptual access. Those remain separate listening-access declarations.
Imported records, receipts and renderings are never mutated by these validators.


The canonical [recipe schema](../packages/core/schemas/transposition-recipe.schema.json)
includes `$defs` for each receipt parameter shape. Validators apply the recipe
shape to the extension and the selected parameter definition to the existing
`OperationReceipt.parameters`, avoiding another copy of those parameters.
`transpositionRecipeErrors` / `transposition_recipe_errors` expose these additional
checks; full graph validation and protected graph writes invoke them as well.
Graph construction/account creation with these annotations additionally requires
`earworm/transposition-recipe/v1` in the supported contract list.
