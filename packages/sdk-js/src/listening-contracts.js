/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

import Ajv from "ajv";
import accessSchema from "@earworm/core/schemas/listening-access.schema.json" with { type: "json" };
import akousmaSchema from "@earworm/core/schemas/akousma.schema.json" with { type: "json" };

export const LISTENING_ACCESS_CONTRACT = "earworm/listening-access/v1";
const ajv = new Ajv({ allErrors: true, strict: false, strictNumbers: true });
ajv.addSchema(akousmaSchema);
export const compileContractSchema = (schema) => ajv.compile(schema);
const validateAccess = ajv.compile(accessSchema);
const validateListening = ajv.compile(akousmaSchema.$defs.auditum.properties.listenings.items);
const validateEnsemble = ajv.compile(akousmaSchema.$defs.auditum.properties.ensemble);
export const schemaErrors = (validate, value) => validate(value) ? [] : validate.errors.map(
  (error) => `${error.instancePath || "<root>"}: ${error.message}`
);

/** Validate declarations without inferring sensing, understanding, or perception. */
export function listeningAccessErrors(value) {
  const errors = schemaErrors(validateAccess, value);
  if (errors.length) return errors;
  for (const [name, bandKey] of [
    ["capture", "supported_band_hz"],
    ["sampled_representation", "retained_band_hz"],
    ["model_input", "effective_band_hz"]
  ]) {
    const block = value[name];
    if (block.status !== "known") continue;
    const band = block[bandKey];
    if (band.lower >= band.upper) errors.push(`${name}/${bandKey}: lower must be less than upper`);
    if (block.sample_rate_hz && band.upper > block.sample_rate_hz / 2) {
      errors.push(`${name}/${bandKey}: exceeds the declared representation's Nyquist limit`);
    }
  }
  if (value.model_input.status === "known" && value.model_input.window_s.start >= value.model_input.window_s.end) {
    errors.push("model_input/window_s: end must be greater than start");
  }
  return errors;
}

/** Call before using required contracts for a decision; opaque retention is not support. */
export function assertSupportedContracts(required, supported) {
  for (const [label, list] of [["required", required], ["supported", supported]]) {
    if (!Array.isArray(list) || list.some((item) => typeof item !== "string" || !item.trim())) {
      throw new TypeError(`${label} contracts must be an array of nonempty strings`);
    }
  }
  const missing = required.filter((contract) => !supported.includes(contract));
  if (missing.length) throw new Error(`Unsupported required contracts: ${missing.join(", ")}`);
}

function indexUnique(items, key, label) {
  if (!Array.isArray(items)) throw new TypeError(`${label} must be an array`);
  const index = new Map();
  for (const item of items) {
    const id = item?.[key];
    if (typeof id !== "string" || !id.trim() || index.has(id)) {
      throw new Error(`${label}: missing or duplicate ${key}`);
    }
    index.set(id, item);
  }
  return index;
}

/**
 * Adapt validated AKOUO passes. Preserve the source payload, map identities explicitly,
 * and check the Earworm output boundary. This is not a full AKOUO schema validator.
 */
export function adaptListeningPasses({ passes, participants, bindings, ensemble = null }) {
  const passIndex = indexUnique(passes, "id", "passes");
  const participantIndex = indexUnique(participants, "id", "participants");
  const bindingIndex = indexUnique(bindings, "pass_id", "bindings");
  indexUnique(bindings, "listening_id", "bindings");
  if (bindingIndex.size !== passIndex.size || [...bindingIndex.keys()].some((id) => !passIndex.has(id))) {
    throw new Error("bindings must map every pass exactly once");
  }
  function mapped(id) {
    const binding = bindingIndex.get(id);
    if (!binding) throw new Error(`Unresolved listening pass: ${id}`);
    return binding.listening_id;
  }
  const listenings = passes.map((pass) => {
    const participant = participantIndex.get(pass.listener_id);
    if (!participant) throw new Error(`Unresolved participant: ${pass.listener_id}`);
    for (const key of ["route", "decision_refs", "influenced_by"]) {
      if (!Array.isArray(pass[key])) throw new Error(`pass.${key} must be an array`);
    }
    const binding = bindingIndex.get(pass.id);
    const listening = {
      listening_id: mapped(pass.id), listener_id: participant.id, listener_type: participant.type,
      created_at: pass.started_at, report_namespace: binding.report_namespace, contract: binding.contract,
      route: structuredClone(pass.route), listening_pass_ref: pass.id,
      route_decision_refs: structuredClone(pass.decision_refs),
      influenced_by: pass.influenced_by.map((influence) => {
        if (influence.pass_id === pass.id) throw new Error("A pass cannot influence itself");
        return { listening_id: mapped(influence.pass_id), effect: influence.effect };
      })
    };
    if (pass.revision_of != null) mapped(pass.revision_of);
    const errors = schemaErrors(validateListening, listening);
    if (errors.length) throw new Error(errors.join("; "));
    return listening;
  });
  let storedEnsemble = null;
  if (ensemble !== null) {
    for (const key of ["participant_ids", "listening_pass_ids", "influence_edges"]) {
      if (!Array.isArray(ensemble[key])) throw new Error(`ensemble.${key} must be an array`);
    }
    const members = new Set(ensemble.listening_pass_ids);
    const actors = new Set(ensemble.participant_ids);
    if (actors.size !== ensemble.participant_ids.length || actors.size < 2 ||
        [...actors].some((id) => !participantIndex.has(id))) throw new Error("Invalid ensemble participants");
    const actualActors = new Set([...members].map((id) => {
      mapped(id);
      return passIndex.get(id).listener_id;
    }));
    if (actors.size !== actualActors.size || [...actualActors].some((id) => !actors.has(id))) {
      throw new Error("Ensemble participants must match the listeners of its passes");
    }
    storedEnsemble = {
      id: ensemble.id, kind: ensemble.kind, listening_ids: ensemble.listening_pass_ids.map(mapped),
      influence_edges: ensemble.influence_edges.map((edge) => {
        if (!members.has(edge.from_pass_id) || !members.has(edge.to_pass_id) || edge.from_pass_id === edge.to_pass_id) {
          throw new Error("Ensemble influence must connect two distinct member passes");
        }
        const target = passIndex.get(edge.to_pass_id);
        if (!target.influenced_by.some((item) => item.pass_id === edge.from_pass_id && item.effect === edge.effect)) {
          throw new Error("Ensemble influence must match its target pass attribution");
        }
        return { from_listening_id: mapped(edge.from_pass_id), to_listening_id: mapped(edge.to_pass_id), effect: edge.effect };
      }),
      permissions_preserved: ensemble.permissions_preserved,
      disagreements_preserved: ensemble.disagreements_preserved,
      dissolution_rule: ensemble.dissolution_rule
    };
    for (const id of members) {
      for (const influence of passIndex.get(id).influenced_by) {
        if (members.has(influence.pass_id) && !ensemble.influence_edges.some((edge) =>
          edge.from_pass_id === influence.pass_id && edge.to_pass_id === id && edge.effect === influence.effect)) {
          throw new Error("Ensemble must retain every influence between its member passes");
        }
      }
    }
    const errors = schemaErrors(validateEnsemble, storedEnsemble);
    if (errors.length) throw new Error(errors.join("; "));
  }
  return {
    listenings, ensemble: storedEnsemble,
    pass_to_listening: Object.fromEntries(bindings.map((item) => [item.pass_id, item.listening_id])),
    source: structuredClone({ passes, participants, ensemble })
  };
}
