/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

/**
 * Akousma helpers for JavaScript/TypeScript consumers (germ UI, algophony
 * dashboard). An akousma is one sound's memory record; the shared store (the
 * akousmata) is documented in docs/akousmata-store.md. The canonical schema is
 * packages/core/schemas/akousma.schema.json; the Python reference
 * implementation (packages/py-akousma) owns store access — these helpers
 * build, check, and link records on the JS side.
 */

export const AKOUSMA_SCHEMA_VERSION = "1.1.0";

export const AKOUSMA_SOURCE_TYPES = [
  "generated",
  "recorded",
  "imported",
  "cloned",
  "designed",
  "unknown"
];

export const AKOUSMA_ORIGINS = [
  "live-input",
  "system-output",
  "file",
  "generated",
  "unknown"
];

export const AKOUSMA_RELATION_TYPES = [
  "variant_of",
  "response_to",
  "same_source_as",
  "recurrence_of",
  "series_with",
  "compares_with",
  "replaces",
  "other"
];

export const AKOUSMA_PIPELINE_EFFECTS = [
  "capture",
  "telephony",
  "acousmatization",
  "amplification",
  "phonofixation",
  "phonogeneration",
  "reshaping"
];

export const GERM_IMPORT_MODES = ["sound", "prompt", "lineage"];

const CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ";

function base32(value, length) {
  let n = BigInt(value);
  const out = [];
  for (let i = 0; i < length; i += 1) {
    out.push(CROCKFORD[Number(n & 31n)]);
    n >>= 5n;
  }
  return out.reverse().join("");
}

/** ULID-style sortable id: 48-bit ms timestamp + 80-bit randomness. */
export function newAkousmaId(prefix = "akm") {
  let random = 0n;
  for (let i = 0; i < 5; i += 1) {
    random = (random << 16n) | BigInt(Math.floor(Math.random() * 0x10000));
  }
  return `${prefix}_${base32(BigInt(Date.now()), 10)}${base32(random, 16)}`;
}

/** Build a valid akousma record (mirrors py-akousma's new_akousma). */
export function createAkousma({
  audio,
  originatingApp,
  sourceType = "recorded",
  origin = "file",
  listening = {},
  parentAkousmaIds = [],
  operation = null,
  prompt = null,
  model = null,
  params = null,
  relations = null,
  tags = [],
  extensions = {},
  sessionId = null,
  summary = null
}) {
  if (!audio || typeof audio.asset_id !== "string" || audio.asset_id.length === 0) {
    throw new Error("createAkousma: audio.asset_id is required");
  }
  if (typeof originatingApp !== "string" || originatingApp.length === 0) {
    throw new Error("createAkousma: originatingApp is required");
  }

  const lineage = { parent_akousma_ids: [...parentAkousmaIds] };
  if (operation) lineage.operation = operation;
  if (prompt) lineage.prompt = prompt;
  if (model) lineage.model = model;
  if (params && Object.keys(params).length > 0) lineage.params = params;
  if (Array.isArray(relations) && relations.length > 0) {
    lineage.relations = relations.map((rel) => ({ ...rel }));
  }

  const record = {
    akousma_id: newAkousmaId(),
    schema_version: AKOUSMA_SCHEMA_VERSION,
    created_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    audio,
    provenance: {
      source_type: sourceType,
      origin,
      originating_app: originatingApp,
      created_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z")
    },
    listening,
    lineage,
    tags: [...tags],
    annotations: {},
    extensions
  };
  if (sessionId) record.session_id = sessionId;
  if (summary) record.summary = summary;
  return record;
}

/** Build a typed lineage relation (kinship link, not causal parenthood). */
export function akousmaRelation(type, targetAkousmaId, note = null) {
  if (!AKOUSMA_RELATION_TYPES.includes(type)) {
    throw new Error(`akousmaRelation: type must be one of ${AKOUSMA_RELATION_TYPES.join(", ")}`);
  }
  const rel = { type, target_akousma_id: targetAkousmaId };
  if (note) rel.note = note;
  return rel;
}

/**
 * Attach a producer's listening entry under its namespace using the v1.1
 * envelope: `{contract?, created_at, summary?, payload}`. Additive — never
 * reshapes another producer's block.
 */
export function addListening(record, namespace, payload, { contract = null, summary = null } = {}) {
  const entry = {
    created_at: new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    payload
  };
  if (contract) entry.contract = contract;
  if (summary) entry.summary = summary;
  record.listening = { ...(record.listening ?? {}), [namespace]: entry };
  return record;
}

/** Minimal shape check (required blocks + enums). Returns [] when valid. */
export function akousmaShapeErrors(record) {
  const errors = [];
  if (!record || typeof record !== "object") return ["record must be an object"];
  for (const key of ["akousma_id", "schema_version", "created_at", "audio", "provenance", "lineage"]) {
    if (!(key in record)) errors.push(`${key}: required property missing`);
  }
  const audio = record.audio;
  if (audio && (typeof audio.asset_id !== "string" || audio.asset_id.length === 0)) {
    errors.push("audio.asset_id: required");
  }
  const provenance = record.provenance ?? {};
  if (provenance.source_type && !AKOUSMA_SOURCE_TYPES.includes(provenance.source_type)) {
    errors.push(`provenance.source_type: expected one of ${AKOUSMA_SOURCE_TYPES.join(", ")}`);
  }
  if (provenance.origin && !AKOUSMA_ORIGINS.includes(provenance.origin)) {
    errors.push(`provenance.origin: expected one of ${AKOUSMA_ORIGINS.join(", ")}`);
  }
  const lineage = record.lineage ?? {};
  if (!Array.isArray(lineage.parent_akousma_ids)) {
    errors.push("lineage.parent_akousma_ids: required array");
  }
  if (lineage.relations !== undefined) {
    if (!Array.isArray(lineage.relations)) {
      errors.push("lineage.relations: expected array");
    } else {
      lineage.relations.forEach((rel, index) => {
        if (!rel || typeof rel !== "object") {
          errors.push(`lineage.relations[${index}]: expected object`);
          return;
        }
        if (!AKOUSMA_RELATION_TYPES.includes(rel.type)) {
          errors.push(`lineage.relations[${index}].type: expected one of ${AKOUSMA_RELATION_TYPES.join(", ")}`);
        }
        if (typeof rel.target_akousma_id !== "string" || rel.target_akousma_id.length === 0) {
          errors.push(`lineage.relations[${index}].target_akousma_id: required`);
        }
      });
    }
  }
  return errors;
}

/** Deep link for handing an akousma to germ (the three oída buttons). */
export function germImportUrl(baseUrl, akousmaId, mode = "sound") {
  if (!GERM_IMPORT_MODES.includes(mode)) {
    throw new Error(`germImportUrl: mode must be one of ${GERM_IMPORT_MODES.join(", ")}`);
  }
  const base = String(baseUrl ?? "").replace(/\/$/, "");
  const params = new URLSearchParams({ akousma: akousmaId, mode });
  return `${base}/import?${params.toString()}`;
}
