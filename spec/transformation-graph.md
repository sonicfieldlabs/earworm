# Application transformation graphs — unreleased draft

`earworm/transformation-graph/v1` maps a retained MASA 0.2.0 record to a versioned
application patch. The canonical [schema](../packages/core/schemas/transformation-graph.schema.json)
defines graph identity, positive safe-integer revision, patch author, explicit
representation-to-node bindings, directed edges and operation references. The
complete source record is retained once in `source_record`.

MASA's versioned specification, schemas and relation registry govern the source.
The host supplies its actual `validateMatterRecord` adapter and exported
`lineageRelationDirections` registry. Python hosts can load that registry from the
installed MASA 0.2.0 ontology and bridge to its validator. Validators run on a
copy, so even a mutating callback cannot rewrite retained source evidence. There
is no copied MASA validator or new `masa:` vocabulary in this application API.

`createTransformationGraph` / `create_transformation_graph` requires explicit
negotiation of this contract and `masa/0.2.0`. `transformationGraphErrors` /
`transformation_graph_errors` validates the application shape, revalidates the
foreign record and recomputes edges. Hosts must use the actual trusted validator
and matching registry; a callback returning no errors is not independent proof
of conformance or source truth. Unit tests stub this boundary; integration tests
exercise MASA itself.

## Scope and direction

Every retained Representation maps to exactly one distinct patch node. This
mapping names a view node, not a replacement material identity. The first version
supports embedded operation history and representation-level `derive`, `transform`,
`render` and `map` effects. Other operations remain in the complete source record
and are not silently converted into transformation edges.

Edges use `from_node` for the source/input and `to_node` for the descendant/output.
Each edge references an existing relation and its operation receipt. Direction
comes from MASA's registry, so `derived-from` and its inverse `derivation-of` can
produce the same input-to-output graph. The endpoints must agree with the
receipt's inputs and outputs. Every completed output needs at least one declared
parent edge; the mapper never invents a Cartesian product of input/output pairs.
Unknown extension relations remain in the source and are not guessed into causal
edges. An output supported only by an unknown-direction relation is rejected as
outside the supported mapping.

Completed operations require preserved input and distinct output Representations.
Refused, failed, cancelled and other incomplete operations with no outputs retain
an operation reference and create no edges. Partial operations with outputs,
external event histories and non-representation processing endpoints require a
future explicit scope; the current mapper rejects them. Incomplete operations
must not be presented as completed transformations.

## Evidence remains in the source

Edges and patch nodes reference existing IDs. They do not duplicate parameters,
engine/version, policy evaluation, affected regions, sample rates, duration,
integrity/hash states, disclosure or reversibility. Those remain in the source
record's receipts and Representations. A graph author is distinct from the
original operation's actors. Graph revision is application metadata; it does not
revise the imported MASA record or establish a monotonic revision history by itself.

In particular, unknown hashes stay unknown, unavailable source bytes stay
unavailable, and interface undo does not become a verified material inverse.
The graph does not perform granulation, filtering, sample-rate conversion,
playback-rate changes, pitch shifting or frequency translation. The existing MASA
processing request and external-engine receipt model remains the execution
boundary. The [transposition receipt recipes](transposition-recipes.md) now add typed
parameter and band/rate checks for four operations; they remain metadata checks
and do not establish engine execution or physical performance.

## Host integration

```javascript
import { createTransformationGraph } from '@earworm/sdk-js';
import { lineageRelationDirections } from '@sonicfield/masa';
import { validateMatterRecord } from '@sonicfield/masa-validator';

const graph = createTransformationGraph(sourceRecord, {
  graph_id: 'patch:example', revision: 1, authored_by: 'author:example',
  nodes: representationNodeBindings,
  supported_contracts: ['earworm/transformation-graph/v1', 'masa/0.2.0']
}, {
  lineageDirections: lineageRelationDirections,
  validateMasa: value => {
    const result = validateMatterRecord(value);
    return result.valid ? [] : result.diagnostics
      .filter(d => d.severity === 'error').map(d => `${d.code}: ${d.message}`);
  }
});
```

Python uses the same graph/options shape with keyword arguments `validate_masa`
and `lineage_directions`. The returned graph is detached from caller inputs.
`transformation_graph_errors` requires the same trusted adapter when consuming a
saved graph, since a structurally valid JSON graph alone is insufficient.

## Protected records and patch revisions

`extensions.earworm_transformation_graph` is now protected in opt-in akousma 1.7
`record_kind: transformation_graph` accounts. `createGraphRecord` /
`create_graph_record` creates an audio-less account without fabricated listening,
raw-audio absence, or authority. The initial graph revision must be 1 and its
`graph_id` equals the root `akousma_id`. This prevents unrelated roots from
silently reusing an existing family identity. The subject identifies that graph.

`reviseGraphRecord` / `revise_graph_record` creates a fresh record with the same
graph family, revision exactly parent + 1, explicit actor/reason/time and an
`auditum.revision` link. It preserves the complete imported MASA source
unchanged at the JSON value level. New source/material evidence starts a distinct
graph family; this patch revision API cannot rewrite imported representations,
receipts or policy metadata. Unknown source fields survive unchanged.

The opt-in schema permits a revision-only auditum for graph artifacts: no
listenings, route decisions, actions, disagreements or absences are fabricated.
Legacy auditum constructors keep their listening/capture requirements. The new
block reuses the existing store revision index and APIs. Revision timestamps
cannot precede the parent. Distinct branches may both advance the same parent;
`revision_heads` exposes them, and `current_head` rejects ambiguity rather than
choosing a winner. Revision numbering is per explicit parent, not global serial
execution or proof of distributed chronology.

The Python store's existing `put` accepts `validate_masa` and `lineage_directions`
keyword arguments, required whenever this graph extension is present. It runs
actual foreign validation, then local graph/revision checks, before writing.
In-place graph addition, removal or mutation is protected by the existing account
comparison; a new patch requires a fresh revision record. Forgotten root IDs
cannot be resurrected. No new graph database or storage pipeline was introduced.

```python
record = create_graph_record(graph, account_options,
    validate_masa=validate_masa, lineage_directions=masa_directions)
store.put(record, validate_masa=validate_masa, lineage_directions=masa_directions)
revision = revise_graph_record(record, patch_revision_options,
    validate_masa=validate_masa, lineage_directions=masa_directions)
store.put(revision, validate_masa=validate_masa, lineage_directions=masa_directions)
```

`nextRecordErrors` and `verify()` check local bindings, including receipt/node
resolution and parent revision increments where the parent is present. They do
not run foreign MASA policy/registry validation; use the full graph validator
before relying on an externally written record. `reindex()` rebuilds the existing
indexes without changing evidence. Public export and patch-editor UI integration
remain separate host responsibilities. No graph term enters the MASA namespace.
