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

export const AKOUSMA_SCHEMA_VERSION = "1.5.0";

export const AUDITUM_CONTRACT = "earworm/auditum/v2";

export const LEGACY_AUDITUM_CONTRACT = "earworm/auditum/v1";

export const AUDITUM_LISTENER_TYPES = ["human", "agent", "hybrid", "community", "institution", "sensor", "habitat", "other_animal", "ensemble", "other"];

export const AUDITUM_ABSENCE_KINDS = [
  "unavailable",
  "withheld",
  "refused",
  "not_retained",
  "forgotten"
];

export const AUDITUM_DISAGREEMENT_STATUSES = ["preserved", "resolved", "undetermined"];

export const AUDITUM_ACTION_STATUSES = ["proposed", "authorized", "refused", "executed", "failed", "reverted"];

export const AUDITUM_DECISION_GATES = ["input", "capture", "inference", "memory", "output", "disclosure", "retention", "action"];

export const AUDITUM_DECISION_OUTCOMES = ["proceed", "pause", "defer", "abstain", "refuse", "withhold", "forget", "do_not_act"];

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

export const AKOUSMA_LOCATION_SOURCES = ["gps", "network", "manual", "config", "inferred"];

export const AKOUSMA_CAPTURE_DIRECTIONS = ["past", "future", "live"];

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
  summary = null,
  location = null,
  capture = null,
  covenant = null,
  auditum = null,
  subject = null
}) {
  if (audio && (typeof audio.asset_id !== "string" || audio.asset_id.length === 0)) {
    throw new Error("createAkousma: audio.asset_id is required when audio is supplied");
  }
  if (!audio) {
    const hasPreCaptureStop = auditum?.contract === AUDITUM_CONTRACT
      && Array.isArray(auditum.route_decisions)
      && auditum.route_decisions.some((decision) => ["input", "capture"].includes(decision.gate) && ["pause", "defer", "abstain", "refuse", "withhold"].includes(decision.outcome));
    if (typeof subject !== "string" || subject.length === 0 || !hasPreCaptureStop) {
      throw new Error("createAkousma: audio may be omitted only with a subject and an auditum/v2 input or capture stop decision");
    }
  }
  if (typeof originatingApp !== "string" || originatingApp.length === 0) {
    throw new Error("createAkousma: originatingApp is required");
  }
  if (location) {
    const problems = locationErrors(location, "location");
    if (problems.length > 0) throw new Error(`createAkousma: ${problems.join("; ")}`);
  }
  if (capture) {
    const problems = captureErrors(capture, "capture");
    if (problems.length > 0) throw new Error(`createAkousma: ${problems.join("; ")}`);
  }
  if (covenant) {
    const problems = covenantErrors(covenant, "covenant");
    if (problems.length > 0) throw new Error(`createAkousma: ${problems.join("; ")}`);
  }
  if (auditum) {
    const problems = auditumErrors(auditum, "auditum");
    if (problems.length > 0) throw new Error(`createAkousma: ${problems.join("; ")}`);
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
  if (audio) record.audio = audio;
  if (subject) record.subject = subject;
  if (sessionId) record.session_id = sessionId;
  if (summary) record.summary = summary;
  if (location) record.location = { ...location };
  if (capture) record.capture = { ...capture };
  if (covenant) record.covenant = { ...covenant };
  if (auditum) record.auditum = structuredClone(auditum);
  return record;
}

/* v1.2 blocks: location (where the sound was heard — consent-scoped) and
 * capture (how the listening was triggered: past/future direction + seconds). */
function locationErrors(location, path) {
  if (!location || typeof location !== "object" || Array.isArray(location)) {
    return [`${path}: expected object`];
  }
  const errors = [];
  if (typeof location.lat !== "number" || location.lat < -90 || location.lat > 90) {
    errors.push(`${path}.lat: expected number in [-90, 90]`);
  }
  if (typeof location.lon !== "number" || location.lon < -180 || location.lon > 180) {
    errors.push(`${path}.lon: expected number in [-180, 180]`);
  }
  if (location.source != null && !AKOUSMA_LOCATION_SOURCES.includes(location.source)) {
    errors.push(`${path}.source: expected one of ${AKOUSMA_LOCATION_SOURCES.join(", ")}`);
  }
  return errors;
}

function captureErrors(capture, path) {
  if (!capture || typeof capture !== "object" || Array.isArray(capture)) {
    return [`${path}: expected object`];
  }
  const errors = [];
  if (capture.direction != null && !AKOUSMA_CAPTURE_DIRECTIONS.includes(capture.direction)) {
    errors.push(`${path}.direction: expected one of ${AKOUSMA_CAPTURE_DIRECTIONS.join(", ")}`);
  }
  if (capture.seconds != null && (typeof capture.seconds !== "number" || capture.seconds < 0)) {
    errors.push(`${path}.seconds: expected number >= 0`);
  }
  return errors;
}

/* v1.3: covenant — under which ethics this was listened. Identity plus honest
 * absence (withheld, counted and attributed, never described). */
function covenantErrors(covenant, path) {
  if (!covenant || typeof covenant !== "object" || Array.isArray(covenant)) {
    return [`${path}: expected object`];
  }
  const errors = [];
  if (typeof covenant.id !== "string" || covenant.id.length === 0) {
    errors.push(`${path}.id: required non-empty string`);
  }
  if (covenant.commitments != null && (!Number.isInteger(covenant.commitments) || covenant.commitments < 0)) {
    errors.push(`${path}.commitments: expected integer >= 0`);
  }
  if (covenant.withheld != null && !Array.isArray(covenant.withheld)) {
    errors.push(`${path}.withheld: expected array`);
  }
  return errors;
}

function auditumErrors(auditum, path) {
  if (!auditum || typeof auditum !== "object" || Array.isArray(auditum)) {
    return [`${path}: expected object`];
  }
  const errors = [];
  const ids = new Set();
  if (![AUDITUM_CONTRACT, LEGACY_AUDITUM_CONTRACT].includes(auditum.contract)) {
    errors.push(`${path}.contract: expected ${LEGACY_AUDITUM_CONTRACT} or ${AUDITUM_CONTRACT}`);
  }
  if (!Array.isArray(auditum.listenings) || (auditum.contract === LEGACY_AUDITUM_CONTRACT && auditum.listenings.length === 0)) {
    errors.push(`${path}.listenings: expected ${auditum.contract === LEGACY_AUDITUM_CONTRACT ? "non-empty " : ""}array`);
  } else {
    auditum.listenings.forEach((listening, index) => {
      for (const key of ["listening_id", "listener_id", "created_at", "report_namespace", "contract"]) {
        if (typeof listening?.[key] !== "string" || listening[key].length === 0) {
          errors.push(`${path}.listenings[${index}].${key}: required non-empty string`);
        }
      }
      if (!AUDITUM_LISTENER_TYPES.includes(listening?.listener_type)) {
        errors.push(`${path}.listenings[${index}].listener_type: expected one of ${AUDITUM_LISTENER_TYPES.join(", ")}`);
      }
      if (ids.has(listening?.listening_id)) {
        errors.push(`${path}.listenings[${index}].listening_id: duplicate`);
      }
      ids.add(listening?.listening_id);
    });
    for (const [index, disagreement] of (auditum.disagreements ?? []).entries()) {
      const listeningIds = disagreement?.listening_ids;
      if (!Array.isArray(listeningIds) || new Set(listeningIds).size < 2) {
        errors.push(`${path}.disagreements[${index}].listening_ids: expected at least two distinct ids`);
      } else if (listeningIds.some((id) => !ids.has(id))) {
        errors.push(`${path}.disagreements[${index}].listening_ids: references unknown listening`);
      }
      if (!AUDITUM_DISAGREEMENT_STATUSES.includes(disagreement?.status)) {
        errors.push(`${path}.disagreements[${index}].status: expected one of ${AUDITUM_DISAGREEMENT_STATUSES.join(", ")}`);
      }
      if (disagreement?.status === "resolved" && (typeof disagreement.resolution_note !== "string" || disagreement.resolution_note.trim().length === 0)) {
        errors.push(`${path}.disagreements[${index}].resolution_note: required non-empty string when resolved`);
      }
      if (!Array.isArray(disagreement?.positions) || disagreement.positions.length < 2) {
        errors.push(`${path}.disagreements[${index}].positions: expected at least two positions`);
      }
    }
  }
  if (!Array.isArray(auditum.disagreements)) errors.push(`${path}.disagreements: expected array`);
  if (!Array.isArray(auditum.honest_absences)) {
    errors.push(`${path}.honest_absences: expected array`);
  } else {
    auditum.honest_absences.forEach((absence, index) => {
      if (!AUDITUM_ABSENCE_KINDS.includes(absence?.kind) && !(auditum.contract === LEGACY_AUDITUM_CONTRACT && absence?.kind === "undetermined")) {
        errors.push(`${path}.honest_absences[${index}].kind: expected one of ${AUDITUM_ABSENCE_KINDS.join(", ")}`);
      }
    });
  }
  if (!Array.isArray(auditum.actions)) {
    errors.push(`${path}.actions: expected array`);
  } else {
    auditum.actions.forEach((action, index) => {
      if (!AUDITUM_ACTION_STATUSES.includes(action?.status)) {
        errors.push(`${path}.actions[${index}].status: expected one of ${AUDITUM_ACTION_STATUSES.join(", ")}`);
      }
    });
  }
  if (auditum.contract === AUDITUM_CONTRACT) {
    if (!Array.isArray(auditum.route_decisions) || auditum.route_decisions.length === 0) {
      errors.push(`${path}.route_decisions: auditum/v2 requires a non-empty array`);
    } else {
      const decisionIds = new Set();
      auditum.route_decisions.forEach((decision, index) => {
        for (const key of ["decision_id", "subject", "reason", "decided_at"]) {
          if (typeof decision?.[key] !== "string" || decision[key].length === 0) {
            errors.push(`${path}.route_decisions[${index}].${key}: required non-empty string`);
          }
        }
        if (!AUDITUM_DECISION_GATES.includes(decision?.gate)) errors.push(`${path}.route_decisions[${index}].gate: invalid`);
        if (!AUDITUM_DECISION_OUTCOMES.includes(decision?.outcome)) errors.push(`${path}.route_decisions[${index}].outcome: invalid`);
        if (decisionIds.has(decision?.decision_id)) errors.push(`${path}.route_decisions[${index}].decision_id: duplicate`);
        decisionIds.add(decision?.decision_id);
        if (decision?.listening_id != null && !ids.has(decision.listening_id)) errors.push(`${path}.route_decisions[${index}].listening_id: references unknown listening`);
        if (typeof decision?.authority?.actor !== "string" || decision.authority.actor.length === 0) errors.push(`${path}.route_decisions[${index}].authority.actor: required`);
      });
      if (auditum.listenings.length === 0 && !auditum.route_decisions.some((decision) => ["input", "capture"].includes(decision.gate) && ["pause", "defer", "abstain", "refuse", "withhold"].includes(decision.outcome))) {
        errors.push(`${path}: empty listenings require an input or capture stop decision`);
      }
    }
    if (auditum.ensemble) {
      if (!Array.isArray(auditum.ensemble.listening_ids) || new Set(auditum.ensemble.listening_ids).size < 2 || auditum.ensemble.listening_ids.some((id) => !ids.has(id))) {
        errors.push(`${path}.ensemble.listening_ids: expected at least two known listenings`);
      }
      if (auditum.ensemble.kind === "ear_swarm" && (!auditum.ensemble.influence_edges?.length || auditum.ensemble.permissions_preserved !== true || auditum.ensemble.disagreements_preserved !== true)) {
        errors.push(`${path}.ensemble: ear_swarm requires influence and preserved permissions/disagreements`);
      }
      for (const edge of auditum.ensemble.influence_edges ?? []) {
        if (!ids.has(edge.from_listening_id) || !ids.has(edge.to_listening_id)) errors.push(`${path}.ensemble.influence_edges: references unknown listening`);
      }
    }
  }
  return errors;
}

/**
 * Build an akousma v1.5 auditum/v2 block. "Tokenized" means structured,
 * attributable, versioned, and addressable — never a financial token.
 */
export function createAuditum({
  listenings = [],
  disagreements = [],
  honestAbsences = [],
  actions = [],
  routeDecisions = [],
  ensemble = null,
  revision = null
}) {
  const block = {
    contract: AUDITUM_CONTRACT,
    listenings: (listenings ?? []).map((item) => ({ ...item })),
    disagreements: disagreements.map((item) => structuredClone(item)),
    honest_absences: honestAbsences.map((item) => ({ ...item })),
    actions: actions.map((item) => structuredClone(item)),
    route_decisions: routeDecisions.map((item) => structuredClone(item))
  };
  if (ensemble) block.ensemble = structuredClone(ensemble);
  if (revision) block.revision = structuredClone(revision);
  const errors = auditumErrors(block, "auditum");
  if (errors.length > 0) throw new Error(`createAuditum: ${errors.join("; ")}`);
  return block;
}

/** Build one addressable auditum/v2 gate decision. */
export function createRouteDecision({
  decisionId,
  gate,
  outcome,
  subject,
  reason,
  actor,
  decidedAt = null,
  authorityMode = "observe_only",
  listeningId = null,
  producerContract = null,
  producerDecisionRef = null,
  covenantRef = null,
  grantedBy = null,
  requiresConfirmation = true,
  reversible = true,
  note = null
}) {
  if (!AUDITUM_DECISION_GATES.includes(gate)) throw new Error(`createRouteDecision: invalid gate ${gate}`);
  if (!AUDITUM_DECISION_OUTCOMES.includes(outcome)) throw new Error(`createRouteDecision: invalid outcome ${outcome}`);
  const decision = {
    decision_id: decisionId,
    gate,
    outcome,
    subject,
    reason,
    decided_at: decidedAt ?? new Date().toISOString().replace(/\.\d{3}Z$/, "Z"),
    authority: {
      mode: authorityMode,
      actor,
      requires_confirmation: Boolean(requiresConfirmation),
      reversible: Boolean(reversible)
    }
  };
  if (listeningId != null) decision.listening_id = listeningId;
  if (producerContract != null) decision.producer_contract = producerContract;
  if (producerDecisionRef != null) decision.producer_decision_ref = producerDecisionRef;
  if (covenantRef != null) decision.authority.covenant_ref = covenantRef;
  if (grantedBy != null) decision.authority.granted_by = grantedBy;
  if (note != null) decision.note = note;
  return decision;
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
  for (const key of ["akousma_id", "schema_version", "created_at", "provenance", "lineage"]) {
    if (!(key in record)) errors.push(`${key}: required property missing`);
  }
  const audio = record.audio;
  if (audio && (typeof audio.asset_id !== "string" || audio.asset_id.length === 0)) {
    errors.push("audio.asset_id: required");
  }
  if (!audio) {
    const decisions = record.auditum?.route_decisions;
    if (typeof record.subject !== "string" || record.subject.length === 0 || record.auditum?.contract !== AUDITUM_CONTRACT || !Array.isArray(decisions) || decisions.length === 0) {
      errors.push("audio or a decision-only subject/auditum is required");
    }
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
  if (record.location !== undefined) {
    errors.push(...locationErrors(record.location, "location"));
  }
  if (record.capture !== undefined) {
    errors.push(...captureErrors(record.capture, "capture"));
  }
  if (record.covenant !== undefined) {
    errors.push(...covenantErrors(record.covenant, "covenant"));
  }
  if (record.auditum !== undefined) {
    errors.push(...auditumErrors(record.auditum, "auditum"));
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
