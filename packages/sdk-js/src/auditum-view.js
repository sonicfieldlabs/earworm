import {record18Errors} from './spectral.js';
/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

import { parseContractInstant } from "./listening-context.js";
import { assertSupportedContracts, compileContractSchema, schemaErrors } from "./listening-contracts.js";
import { nextRecordErrors } from "./record-evolution.js";
import legacySchema from "@earworm/core/schemas/akousma.schema.json" with { type: "json" };

export const AUDITUM_VIEW_CONTRACT = "earworm/auditum-view/v1";
export const FORGETTING_RECEIPT_CONTRACT = "earworm/forgetting-receipt/v1";
const validateLegacy = compileContractSchema(legacySchema);
const flags = ["record_deleted", "audio_deletion_requested", "audio_deleted", "shared_audio_preserved"];
const identifier = (value) => typeof value === "string" && value.trim().length > 0;

/** Allowlist metadata only. Free-text actor/reason/recovery and unknown fields stay private. */
export function forgettingReceiptView(receipt, recordId) {
  if (!identifier(recordId) || receipt?.contract !== FORGETTING_RECEIPT_CONTRACT ||
      receipt.akousma_id !== recordId || !identifier(receipt.receipt_id) ||
      flags.some((key) => typeof receipt[key] !== "boolean") || receipt.record_deleted !== true) {
    throw new Error("Invalid forgetting receipt identity, contract or deletion flags");
  }
  parseContractInstant(receipt.created_at);
  if ((receipt.audio_deleted || receipt.shared_audio_preserved) && !receipt.audio_deletion_requested ||
      receipt.audio_deleted && receipt.shared_audio_preserved) {
    throw new Error("Inconsistent forgetting receipt audio outcome");
  }
  return Object.fromEntries(["contract", "receipt_id", "akousma_id", "created_at", ...flags]
    .map((key) => [key, receipt[key]]));
}

/** One-hop record references only; asset, listening and foreign MASA IDs are not store IDs. */
function references(record) {
  const refs = [...(record.lineage?.parent_akousma_ids ?? []),
    ...(record.lineage?.relations ?? []).map((r) => r.target_akousma_id),
    record.auditum?.revision?.revises_akousma_id];
  if (["1.7.0","1.8.0"].includes(record.schema_version)) {
    refs.push(record.auditum?.appeal?.legacy_source?.record_ref);
    const decision = record.extensions?.earworm_generation_decision;
    if (decision) refs.push(decision.generation_ref, ...decision.subsequent_listenings.map((r) => r.record_ref));
    for (const relation of record.lineage?.relations ?? []) {
      for (const ref of relation.criterion?.descriptor_refs ?? []) refs.push(ref.record_ref);
    }
  }
  return [...new Set(refs.filter((ref) => identifier(ref) && ref !== record.akousma_id))].sort();
}

/** Synchronous local view. Host permission is checked before either resolver runs. */
export function auditumView(recordId, { readRecord, readReceipt, canRead, supported_contracts }) {
  assertSupportedContracts([AUDITUM_VIEW_CONTRACT, FORGETTING_RECEIPT_CONTRACT], supported_contracts);
  if (!identifier(recordId) || [readRecord, readReceipt, canRead].some((fn) => typeof fn !== "function")) {
    throw new TypeError("Record ID, record/receipt resolvers and an explicit permission callback are required");
  }
  function resolve(id) {
    const permitted = canRead(id);
    if (typeof permitted !== "boolean") throw new TypeError("canRead must return a boolean");
    if (!permitted) return { entry: { record_ref: id, state: "withheld" } };
    const record = readRecord(id);
    if (record !== null) {
      const errors = record?.schema_version === "1.8.0" ? record18Errors(record) : record?.schema_version === "1.7.0" ? nextRecordErrors(record) : ["1.0.0","1.1.0","1.2.0","1.3.0","1.4.0","1.5.0","1.6.0"].includes(record?.schema_version) ? schemaErrors(validateLegacy, record) : ["Unsupported record schema version"];
      if (errors.length || record.akousma_id !== id) throw new Error("Invalid or mismatched resolved record");
      return { entry: { record_ref: id, state: "available" }, record };
    }
    const receipt = readReceipt(id);
    return { entry: receipt === null ? { record_ref: id, state: "unavailable" } :
      { record_ref: id, state: "forgotten", receipt: forgettingReceiptView(receipt, id) } };
  }
  const root = resolve(recordId);
  return { contract: AUDITUM_VIEW_CONTRACT, ...root.entry,
    ...(root.record ? { auditum: structuredClone(root.record.auditum ?? null),
      references: references(root.record).map((id) => resolve(id).entry) } : {}) };
}
