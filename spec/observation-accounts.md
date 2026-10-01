# Observation accounts and matter context — unreleased draft

`earworm/observation-account/v1` binds the opt-in akousma 1.7
`record_kind: observation_account` to a retained
`akouo/masa-observation-report/v0.1` mapping. It is an explicit account of structured
observation data, including non-acoustic data. It requires neither a fabricated
audio asset nor an invented raw-audio absence or capture refusal. Released akousma
1.6 schemas and default constructors are unchanged.

The mapping is stored once, as the payload of its namespaced `listening` entry.
It includes the complete validated MASA source, its original qualifications and
unknown extensions, and the separately attributable AKOÚŌ report. The auditum names
the receiving listener and pass. `extensions.earworm_observation` identifies the
source MASA record, Observation, mapping, report and local listening. This is a
foreign-source binding, not an akousma-to-akousma edge: never insert a MASA URI into
`target_akousma_id`, manufacture a causal parent, or reinterpret retention as a new
physical observation. MASA names remain owned by MASA; this mapping stays in the
Earworm application namespace.

The caller must supply a successful retained route decision, a matching access
declaration, and explicit record/listening identities. The constructor does not
execute or invent those decisions. It uses the supplied AKOÚŌ mapping validator,
which in turn must use the actual MASA validator. This reuses the foreign contracts
without copying their schemas into Earworm. A host remains responsible for local
read/write authority and the truth and permitted disclosure of source evidence.

`earworm/matter-context/v1` preserves the MASA 0.2.0 source's register and scale
labels verbatim, including namespaced labels. The core values are sourced from
MASA 0.2.0's normative record schema and spec section 6. No synonym table silently
converts `microtemporal` into auditory `sample`, `cosmic` into hearing, or
`physical-event` into a certified physical capture.

The context separates these declarations:

- `source_modality`: qualified acoustic, non-acoustic or mixed origin, with evidence.
- `representation`: qualified structured-observation input and its Observation ID.
- `access_declaration_ref`: the existing Earworm declaration; capture support,
  sampled signal, effective model input and human access remain separate there.
- `temporal_scope`: a qualified window, resolution, sample rate and evidence
  domain. Reported scope, mathematical construction, sampled representation and
  physical observation have different meanings. Unknown scope remains unknown.

Known temporal bounds must increase; resolution and sample rate must be positive.
A sampled-representation or physical-observation resolution below a declared
sample interval is rejected. A sub-sample numerical construction can retain its
finer grid only as `mathematical_construction`; it does not establish sensing.
Physical acoustic scope also requires known capture support and apparatus evidence
in the existing access declaration. Non-acoustic physical scope requires explicit
source-method apparatus evidence, not an invented audio capture. Neither a label
nor passing these consistency checks proves physical performance or human access.

The record-local validators check the binding and context against the retained
mapping, auditum and access declaration. The external-contract checker additionally
runs the injected mapping validator and can compare the snapshot to the separately
retained original source. Ordinary store reads and reindexing preserve the mapping;
store writes protect the observation binding, matter context and listening payload
against in-place replacement or deletion. Revision uses the existing explicit
revision mechanism. Curatorial summary/tags remain editable.

Generic record validation establishes Earworm structure and local binding, not
foreign MASA or AKOÚŌ conformance. Validate foreign contracts at ingress and again
before relying on imported data from another writer. The opt-in [agent-sector
extension](agent-sectors.md) now resolves sector renderings and typed measurement
descriptors. Dispatch and end-user observation navigation remain integration work.

## APIs and validation scope

JavaScript exports `createObservationAccount(mapping, options, validateMapping)`,
`observationAccountErrors(record, validateMapping)` and
`matterContextErrors(context, sourceRecord, access)` from the SDK root. Python
exports their snake-case equivalents from `akousma.observation_accounts`.

The options provide `supported_contracts`, `akousma_id`, `created_at`,
`originating_app`, `listening_id`, `matter_context_id`, an Earworm-shaped
`route_decision`, `access`, `source_modality`, `representation` and
`temporal_scope`. See the shared `tests/contracts/observations/account.json`
fixture for a complete example. A missing field is not permission to invent it.

`validateMapping` / `validate_mapping` must synchronously return a list of error
strings. Use AKOÚŌ's `masa_observation_report_errors`, configured with the actual
MASA validator and optionally the separately retained original `source_record`.
The constructor and full checker reject foreign-validation errors. Generic store
validation does not replace that callback or silently install a second foreign
validator. JSON Schema checks and reference binding alone do not establish source
truth, provenance authenticity, host authorization or disclosure rights.

The Python store's protected comparison now distinguishes JSON booleans from
numbers, so `false` cannot replace `0` (or `true` replace `1`) in retained evidence.
