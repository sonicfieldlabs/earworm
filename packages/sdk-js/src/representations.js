/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */
import { createHash } from "node:crypto";
import Ajv from "ajv";
import representation from "@earworm/core/schemas/representation.schema.json" with { type: "json" };
import access from "@earworm/core/schemas/representation-access.schema.json" with { type: "json" };
import output from "@earworm/core/schemas/representation-output.schema.json" with { type: "json" };
import bundle from "@earworm/core/schemas/representation-record.schema.json" with { type: "json" };
import measurement from "@earworm/core/schemas/representation-measurement.schema.json" with { type: "json" };
import record19 from "@earworm/core/schemas/akousma-1.9.schema.json" with { type: "json" };
import { assertSupportedContracts, schemaErrors } from "./listening-contracts.js";
import { record18Errors } from "./spectral.js";

export const REPRESENTATION_SCHEMA_VERSION = "1.9.0";
export const REPRESENTATION_CONTRACTS = Object.freeze([
  "earworm/representation/v1", "earworm/representation-access/v1",
  "earworm/representation-output/v1", "earworm/representation-record/v1",
  "earworm/akousma/v1.9"
]);
const ajv = new Ajv({ allErrors: true, strict: false, strictNumbers: true });
for (const schema of [representation, access, output, bundle, measurement, record19]) ajv.addSchema(schema);
const textForms = new Set(["text", "notation", "data", "morse", "glyphs", "code"]);
const finite = value => typeof value === "number" ? Number.isFinite(value) :
  value && typeof value === "object" ? Object.values(value).every(finite) : true;
const shape = (schema, value) => finite(value) ? schemaErrors(ajv.getSchema(schema.$id), value) : ["Nonfinite representation value"];
const digest = bytes => createHash("sha256").update(bytes).digest("hex");

export function representationErrors(value) {
  const errors = shape(representation, value);
  if (errors.length) return errors;
  const artifact = value.artifact;
  if (textForms.has(value.form) && !Object.hasOwn(value, "encoding")) errors.push("Textual representation requires an explicit encoding");
  if (Object.hasOwn(artifact, "inline_text")) {
    if (artifact.state !== "retained" || !textForms.has(value.form) || value.encoding !== "utf-8") {
      errors.push("Inline text requires a retained UTF-8 textual representation");
    }
    if ([...artifact.inline_text].some(char => char.codePointAt(0) >= 0xd800 && char.codePointAt(0) <= 0xdfff)) {
      errors.push("Inline text contains an unpaired Unicode surrogate");
    } else {
      const bytes = Buffer.from(artifact.inline_text, "utf-8");
      if (digest(bytes) !== artifact.sha256 || bytes.length !== artifact.byte_count) errors.push("Inline text digest or byte count mismatch");
    }
  }
  if (value.preservation.layout === "preserved" && value.preservation.losses.length) errors.push("Preserved layout cannot declare layout losses");
  if (value.preservation.layout === "transformed" && value.origin.kind !== "transformed") errors.push("Transformed layout requires a declared transformation origin");
  for (const basis of value.time_basis) {
    if (basis.kind === "unknown" && !Object.hasOwn(basis, "reason")) errors.push("Unknown time basis requires a reason");
    if (basis.extent && (!basis.unit || basis.extent.start > basis.extent.end)) errors.push("Time extent requires units and ordered bounds");
    if (["source_event", "capture", "execution"].includes(basis.kind) && !basis.clock_ref) errors.push("Event time requires an explicit clock");
  }
  return errors;
}

export const representationMeasurementErrors = value => shape(measurement, value);

/** Check the closed declared scope. This does not prove attention or prose truth. */
export function representationRecordErrors(value) {
  const errors = shape(bundle, value);
  if (errors.length) return errors;
  const reps = new Map(value.representations.map(r => [r.representation_id, r]));
  const accesses = new Map(value.accesses.map(a => [a.access_id, a]));
  const bindings = new Map(value.binding_refs.map(b => [b.binding_id, b]));
  const identifiers = [
    ...value.representations.map(r => r.representation_id), ...value.accesses.map(a => a.access_id),
    ...value.relations.map(r => r.relation_id), ...value.outputs.map(o => o.output_id),
    ...value.binding_refs.map(b => b.binding_id)
  ];
  if (new Set(identifiers).size !== identifiers.length) errors.push("Duplicate representation-scope identity");
  for (const rep of reps.values()) errors.push(...representationErrors(rep));
  const graph = new Map([...reps.keys()].map(key => [key, []]));
  for (const relation of value.relations) {
    const child = relation.from_ref, parent = relation.to_ref;
    if (!reps.has(child) || !reps.has(parent) || child === parent) {
      errors.push("Relation requires two distinct resolved representations"); continue;
    }
    graph.get(child).push(parent);
    if (relation.kind === "transformed_from") {
      if (!relation.method_ref || !Object.hasOwn(relation, "losses")) errors.push("Transformation requires a method and declared losses");
      if (reps.get(child).origin.kind !== "transformed" || !reps.get(child).origin.source_refs.includes(parent)) {
        errors.push("Transformation origin must identify its parent representation");
      }
    }
  }
  const incoming = new Map([...reps.keys()].map(key => [key, 0]));
  for (const parents of graph.values()) for (const parent of parents) incoming.set(parent, incoming.get(parent) + 1);
  const ready = [...incoming.keys()].filter(key => incoming.get(key) === 0);
  let visited = 0;
  while (ready.length) {
    const key = ready.pop(); visited++;
    for (const parent of graph.get(key)) {
      incoming.set(parent, incoming.get(parent) - 1);
      if (incoming.get(parent) === 0) ready.push(parent);
    }
  }
  if (visited !== reps.size) errors.push("Cyclic representation lineage");
  for (const rep of reps.values()) {
    if (rep.origin.kind === "transformed" && !value.relations.some(r => r.kind === "transformed_from" && r.from_ref === rep.representation_id)) {
      errors.push("Transformed representation requires explicit lineage");
    }
  }
  for (const binding of bindings.values()) {
    const document = reps.get(binding.document_representation_ref);
    if (!document || document.artifact.sha256 !== binding.document_sha256) errors.push("Binding must identify the complete document digest");
    if (binding.scope.kind === "invocation" && binding.scope.ref !== value.operation_ref) errors.push("Invocation binding must identify this operation");
  }
  const available = [];
  for (const access of accesses.values()) {
    const source = reps.get(access.representation_ref), received = reps.get(access.received_representation_ref);
    const coverage = access.coverage;
    if (access.operation_ref !== value.operation_ref || !source) errors.push("Access operation or source is unresolved");
    if (access.status === "available") {
      available.push(access);
      if (!received || coverage.kind === "none") errors.push("Available access requires actual supplied material");
      else if (["withheld", "unknown"].includes(received.artifact.state)) errors.push("Available access cannot receive withheld or unknown material");
      else if (!Object.hasOwn(received.artifact, "sha256") || !Object.hasOwn(received.artifact, "byte_count")) errors.push("Available access requires exact received-byte identity");
      if (coverage.kind === "full" && access.received_representation_ref !== access.representation_ref) errors.push("Full access must name the original representation");
      if (coverage.kind === "partial") {
        if (!coverage.ranges.length || coverage.unit === "unknown" || received === source) errors.push("Partial access requires ranges and a distinct derivative");
        if (!value.relations.some(r => r.kind === "transformed_from" && r.from_ref === access.received_representation_ref && r.to_ref === access.representation_ref)) {
          errors.push("Partial access requires a declared transformation");
        }
      }
    } else if (access.received_representation_ref || coverage.kind !== "none" || coverage.ranges.length || !access.reason) {
      errors.push("Unavailable access must declare none and its reason");
    }
    let previous = -1;
    for (const interval of coverage.ranges) {
      if (interval.start >= interval.end || interval.start < previous) errors.push("Coverage ranges must be ordered, nonempty and disjoint");
      previous = interval.end;
      if (source && coverage.unit === "byte" && interval.end > (source.artifact.byte_count ?? -1)) errors.push("Coverage exceeds the declared source bytes");
    }
    if (coverage.kind === "full" && (coverage.omissions.length || (coverage.ranges.length && (
      coverage.ranges.length !== 1 || coverage.ranges[0].start !== 0 ||
      (source && coverage.unit === "byte" && coverage.ranges[0].end !== source.artifact.byte_count)
    )))) errors.push("Full access cannot omit or truncate material");
    if (access.role === "instruction") {
      const binding = bindings.get(access.binding_ref);
      if (!binding || binding.document_representation_ref !== access.representation_ref) errors.push("Instruction role requires its explicit document binding");
    } else if (Object.hasOwn(access, "binding_ref")) errors.push("A source or context cannot activate an instruction binding");
  }
  for (const output of value.outputs) {
    const rep = reps.get(output.representation_ref);
    if (output.operation_ref !== value.operation_ref || !rep) errors.push("Output operation or representation is unresolved");
    const inputs = output.input_access_refs.map(key => accesses.get(key));
    if (inputs.some(a => !a || a.status !== "available")) errors.push("Output inputs must resolve to available accesses");
    if (inputs.some(a => a?.received_representation_ref === output.representation_ref)) errors.push("Output requires a new representation identity");
    if (output.completion === "complete" && rep && rep.artifact.state !== "retained") errors.push("Complete output requires the retained complete artifact");
    const expected = output.kind === "account" ? "account_of" : "response_to";
    if (["account", "work"].includes(output.kind) && !value.relations.some(r => r.kind === expected && r.from_ref === output.representation_ref && inputs.some(a => a?.received_representation_ref === r.to_ref))) {
      errors.push("Account or work requires its declared source relation");
    }
  }
  const status = value.outcome.status;
  if (status === "completed" && (!value.outputs.length || value.outputs.some(o => o.completion !== "complete"))) errors.push("Completed outcome requires complete outputs");
  if (["no_response", "refused", "withheld", "missing", "source_only", "pending"].includes(status) && value.outputs.length) errors.push("This outcome cannot carry completed or partial outputs");
  if (status === "no_response" && !available.length) errors.push("No-response outcome requires declared available material");
  if (["refused", "missing", "source_only"].includes(status) && available.length) errors.push("A refusal, missing history or source-only record cannot claim material was supplied");
  const returned = value.return;
  if (returned) {
    if (returned.previous_operation_ref === value.operation_ref) errors.push("A return must identify another operation");
    if (!available.some(a => a.representation_ref === returned.representation_ref && ["subject", "score", "work"].includes(a.role))) errors.push("Return subject must be an available primary input");
    if (returned.context_basis === "independent" && returned.context_access_refs.length) errors.push("Independent return cannot supply earlier accounts");
    if (returned.context_basis === "independent" && available.some(a => a.role === "account")) errors.push("Independent return cannot receive an account as context");
    if (["informed", "shared_analysis"].includes(returned.context_basis) && !returned.context_access_refs.length) errors.push("Informed or shared return requires declared context");
    for (const key of returned.context_access_refs) {
      const a = accesses.get(key);
      if (!a || a.status !== "available" || !["account", "context"].includes(a.role)) errors.push("Return context must resolve to an available account or context");
    }
  }
  return errors;
}

export function record19Errors(record, { validateNative, resolveObject } = {}) {
  const errors = shape(record19, record);
  if (errors.length) return errors;
  const block = record.extensions?.earworm_representation;
  if (block) {
    errors.push(...representationRecordErrors(block));
    if (block.record_ref !== record.akousma_id) errors.push("Representation block belongs to another record");
  }
  if (record.record_kind === "representation_record") {
    const reserved = ["earworm_research", "earworm_generation_decision", "earworm_observation", "earworm_agent_sector", "earworm_transformation_graph", "oida.spectral", "akouo.agent-native", "earworm_listening_access", "earworm_listening_context"];
    if (reserved.some(key => Object.hasOwn(record.extensions, key)) || ["audio", "auditum", "listening"].some(key => Object.hasOwn(record, key))) {
      errors.push("Representation records cannot impersonate legacy audio or auditum paths");
    }
  } else {
    const legacy = structuredClone(record); legacy.schema_version = "1.8.0";
    if (legacy.extensions) delete legacy.extensions.earworm_representation;
    errors.push(...record18Errors(legacy, { validateNative, resolveObject }));
  }
  return errors;
}

/** Admit bytes through a host resolver, without fetching or adopting anything. */
export function admitRepresentationRecord(value, { supportedContracts, resolveArtifact, validateBinding, resolveOperation } = {}) {
  assertSupportedContracts(REPRESENTATION_CONTRACTS, supportedContracts);
  const errors = representationRecordErrors(value);
  if (errors.length) throw new Error(errors.join("; "));
  const reps = new Map(value.representations.map(r => [r.representation_id, r]));
  const required = new Set(value.accesses.filter(a => a.status === "available").map(a => a.received_representation_ref));
  for (const output of value.outputs) required.add(output.representation_ref);
  for (const key of [...required].sort()) {
    const rep = reps.get(key), artifact = rep.artifact;
    const bytes = Object.hasOwn(artifact, "inline_text") ? Buffer.from(artifact.inline_text, "utf-8") : resolveArtifact?.(structuredClone(rep));
    if (!(bytes instanceof Uint8Array) || digest(bytes) !== artifact.sha256 || bytes.length !== artifact.byte_count) {
      errors.push("Supplied artifact bytes are unavailable or mismatched: " + key); continue;
    }
    if (rep.encoding === "utf-8") {
      try { new TextDecoder("utf-8", { fatal: true }).decode(bytes); }
      catch { errors.push("Supplied artifact is not valid UTF-8: " + key); }
    }
  }
  for (const access of value.accesses) {
    if (access.role === "instruction") {
      const binding = value.binding_refs.find(b => b.binding_id === access.binding_ref);
      const result = validateBinding?.(structuredClone(binding), structuredClone(access));
      if (!Array.isArray(result) || result.some(e => typeof e !== "string")) errors.push("Instruction binding has not been validated by its owner");
      else errors.push(...result);
    }
  }
  const returned = value.return;
  if (returned) {
    const previous = resolveOperation?.(returned.previous_operation_ref);
    if (!previous || previous.operation_ref !== returned.previous_operation_ref) errors.push("Return operation is unresolved by its owner");
    else if (returned.kind === "original" && previous.primary_representation_ref !== returned.representation_ref) errors.push("Original return must resolve to the previous subject");
    else {
      const outputs = previous.output_representation_refs ?? [], accounts = previous.account_representation_refs ?? [];
      if (!Array.isArray(outputs) || !Array.isArray(accounts) || [...outputs, ...accounts].some(x => typeof x !== "string")) errors.push("Return owner references must be arrays of identities");
      else if (returned.kind === "descendant" && !outputs.includes(returned.representation_ref)) errors.push("Descendant return must resolve to a previous output");
      if (Array.isArray(accounts) && returned.context_basis === "independent" && value.accesses.some(a => a.status === "available" && (accounts.includes(a.received_representation_ref) || accounts.includes(a.representation_ref)))) errors.push("Independent return received a prior account");
    }
  }
  if (errors.length) throw new Error(errors.join("; "));
  return structuredClone(value);
}
