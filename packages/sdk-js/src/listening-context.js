/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */
import schema from "@earworm/core/schemas/listening-context.schema.json" with { type: "json" };
import { compileContractSchema, schemaErrors, listeningAccessErrors } from "./listening-contracts.js";

export const LISTENING_CONTEXT_CONTRACT = "earworm/listening-context/v1";
const validateContext = compileContractSchema(schema);
const validateClaim = compileContractSchema(schema.properties.claims.items);

// A deliberately narrow, language-neutral timestamp profile: UTC, millisecond precision.
function instant(value) {
  if (typeof value !== "string" || !/^[1-9]\d{3}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{3})?Z$/.test(value)) {
    throw new TypeError("Expected a UTC timestamp YYYY-MM-DDTHH:mm:ss[.SSS]Z");
  }
  const timestamp = Date.parse(value);
  const normalized = value.includes(".") ? value : value.replace("Z", ".000Z");
  if (!Number.isFinite(timestamp) || new Date(timestamp).toISOString() !== normalized) {
    throw new TypeError("Invalid calendar timestamp");
  }
  return timestamp;
}

function claimErrors(claim) {
  const errors = schemaErrors(validateClaim, claim);
  if (errors.length) return errors;
  try {
    if (claim.validity.status !== "unknown") instant(claim.validity.issued_at);
    if (claim.validity.status === "expires" && instant(claim.validity.expires_at) <= instant(claim.validity.issued_at)) {
      errors.push("claim expiry must follow issuance");
    }
    if (claim.retention.status === "review_after") instant(claim.retention.review_after);
  } catch (error) { errors.push(error.message); }
  return errors;
}

/** Check the companion and its record-local links; never fetch external references. */
export function listeningContextErrors(value, record) {
  const errors = schemaErrors(validateContext, value);
  if (errors.length) return errors;
  const listenings = record?.auditum?.listenings;
  if (!Array.isArray(listenings)) return ["record.auditum.listenings is required for reference validation"];
  if (listenings.some((item) => !item || typeof item.listening_id !== "string" || typeof item.contract !== "string")) return ["invalid record listening reference"];
  const listeners = new Map(listenings.map((item) => [item.listening_id, item]));
  const seen = new Set();
  const renderingIds = new Set();
  const primaryAccess = record?.extensions?.earworm_listening_access;
  const declarations = [...(primaryAccess === undefined ? [] : [primaryAccess]), ...(value.access_declarations ?? [])];
  const accessById = new Map();
  for (const declaration of declarations) {
    if (listeningAccessErrors(declaration).length) {
      errors.push("record has an invalid listening access declaration");
      continue;
    }
    if (accessById.has(declaration.declaration_id)) errors.push("access declaration id is duplicated");
    accessById.set(declaration.declaration_id, declaration);
  }
  for (const context of value.contexts) {
    const listening = listeners.get(context.listening_ref);
    const access = accessById.get(context.access_declaration_ref);
    if (!listening || seen.has(context.listening_ref)) errors.push("context listening_ref is missing or duplicated");
    seen.add(context.listening_ref);
    if (context.access_declaration_ref !== access?.declaration_id) errors.push("unresolved access_declaration_ref");
    if (context.subject_ref !== access?.subject_ref) errors.push("context subject does not match its access declaration");
    if (listening && context.report.contract !== listening.contract) errors.push("report contract does not match its listening");
    const recipientIds = context.recipients.map((recipient) => recipient.id);
    if (new Set(recipientIds).size !== recipientIds.length) errors.push("recipient id is duplicated");
    const localRenderings = new Set();
    for (const rendering of context.renderings) {
      if (renderingIds.has(rendering.rendering_id)) errors.push("rendering_id is duplicated");
      renderingIds.add(rendering.rendering_id);
      localRenderings.add(rendering.rendering_id);
      if (rendering.source_ref === rendering.output_ref) errors.push("rendering must identify a distinct output");
    }
    if (context.report.human_rendering.status === "available") {
      for (const ref of context.report.human_rendering.rendering_refs) {
        if (!localRenderings.has(ref)) errors.push("human rendering reference is unresolved in this context");
      }
    }
  }
  if (seen.size !== listeners.size || listenings.length !== listeners.size) errors.push("contexts must cover each unique record listening exactly once");
  const claims = new Set();
  for (const claim of value.claims) {
    if (claims.has(claim.claim_ref)) errors.push("claim_ref is duplicated");
    claims.add(claim.claim_ref);
    if (!seen.has(claim.listening_ref)) errors.push("claim listening_ref is unresolved");
    errors.push(...claimErrors(claim));
  }
  return errors;
}

/** Claim currency is independent of factual truth, retention and action authority. */
export function claimValidityAt(claim, now) {
  const errors = claimErrors(claim);
  if (errors.length) throw new TypeError(errors.join("; "));
  const time = instant(now);
  if (claim.validity.status === "unknown") return "unknown";
  if (time < instant(claim.validity.issued_at)) return "not_yet_valid";
  if (claim.validity.status === "expires" && time >= instant(claim.validity.expires_at)) return "expired";
  return "current";
}

/** A review date never authorizes deletion; use the existing retention/forgetting path. */
export function claimRetentionAt(claim, now) {
  const errors = claimErrors(claim);
  if (errors.length) throw new TypeError(errors.join("; "));
  const time = instant(now);
  if (claim.retention.status !== "review_after") return "policy_required";
  return time >= instant(claim.retention.review_after) ? "review_due" : "review_not_due";
}

// Shared internally by versioned record chronology validation.
export { instant as parseContractInstant };
