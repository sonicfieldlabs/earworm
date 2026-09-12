/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

import type {
  AssetRef,
  ContextSelector,
  EarwormEvent,
  EarwormSession,
  EventStore,
  ManifestScope,
  ProvenanceRecord,
  RetentionPolicy
} from "@earworm/core";

export class EarwormClient {
  constructor(input?: { session?: EarwormSession; store?: EventStore });
  static create(input: {
    session_id: string;
    app_id: string;
    policy: RetentionPolicy;
    created_at?: string;
    assets?: AssetRef[];
    provenance?: ProvenanceRecord[];
  }): EarwormClient;
  readonly session_id: string;
  readonly store: EventStore;
  readonly session: EarwormSession;
  readonly events: readonly EarwormEvent[];
  append(event: EarwormEvent): string;
  ingestPrompt(input: unknown): string;
  ingestGenerationRequest(input: unknown): string;
  ingestGeneratedAsset(input: unknown): string;
  ingestAlignment(input: unknown): string;
  ingestSignalPacket(input: unknown): string;
  ingestAnalysis(input: unknown): string;
  emitModulationIntent(input: unknown): string;
  commitAutomation(input: unknown): string;
  revertAutomation(laneEventId: string, input?: unknown): string;
  recordAgentAction(input: unknown): string;
  createSnapshot(input: unknown): string;
  queryContext(selector?: ContextSelector): unknown;
  exportManifest(scope?: ManifestScope): unknown;
}

export * from "@earworm/core";

/* ── Akousma (one sound's memory record; see docs/akousma_spec_v1.md) ── */

export const AKOUSMA_SCHEMA_VERSION: string;
export const AKOUSMA_SOURCE_TYPES: readonly string[];
export const AKOUSMA_ORIGINS: readonly string[];
export const AKOUSMA_RELATION_TYPES: readonly string[];
export const AKOUSMA_PIPELINE_EFFECTS: readonly string[];
export const AKOUSMA_LOCATION_SOURCES: readonly string[];
export const AKOUSMA_CAPTURE_DIRECTIONS: readonly string[];
export const AUDITUM_CONTRACT: "earworm/auditum/v2";
export const LEGACY_AUDITUM_CONTRACT: "earworm/auditum/v1";
export const AUDITUM_LISTENER_TYPES: readonly string[];
export const AUDITUM_ABSENCE_KINDS: readonly string[];
export const AUDITUM_DISAGREEMENT_STATUSES: readonly string[];
export const AUDITUM_ACTION_STATUSES: readonly string[];
export const AUDITUM_DECISION_GATES: readonly string[];
export const AUDITUM_DECISION_OUTCOMES: readonly string[];
export const AKOUSMA_RECORD_CLASSES: readonly AkousmaRecordClass[];
export const GERM_IMPORT_MODES: readonly ["sound", "prompt", "lineage"];

export type AkousmaRecordClass =
  | "human"
  | "agent"
  | "hybrid"
  | "plural_other"
  | "decision_only"
  | "legacy";

export interface AkousmaAudio {
  asset_id: string;
  type?: string;
  uri?: string;
  content_hash?: string;
  duration_seconds?: number;
  sample_rate?: number;
  channels?: number;
  provenance_id?: string;
}

export interface AkousmaProvenance {
  provenance_id?: string;
  source_type: "generated" | "recorded" | "imported" | "cloned" | "designed" | "unknown";
  origin: "live-input" | "system-output" | "file" | "generated" | "unknown";
  originating_app: string;
  device?: string;
  provider?: string;
  model_id?: string;
  seed?: number;
  consent_status?: "owned" | "licensed" | "public_domain" | "unknown" | "restricted";
  created_at?: string;
  capture_conditions?: string;
  rights_note?: string;
  pipeline_effects?: AkousmaPipelineEffect[];
}

export type AkousmaPipelineEffect =
  | "capture"
  | "telephony"
  | "acousmatization"
  | "amplification"
  | "phonofixation"
  | "phonogeneration"
  | "reshaping";

export type AkousmaRelationType =
  | "variant_of"
  | "response_to"
  | "same_source_as"
  | "recurrence_of"
  | "series_with"
  | "compares_with"
  | "replaces"
  | "other";

export interface AkousmaRelation {
  type: AkousmaRelationType;
  target_akousma_id: string;
  note?: string;
}

export interface AkousmaLineage {
  parent_akousma_ids: string[];
  operation?: string;
  prompt?: string;
  model?: string;
  params?: Record<string, unknown>;
  relations?: AkousmaRelation[];
  event_ids?: string[];
}

export interface AkousmaLocation {
  lat: number;
  lon: number;
  accuracy_m?: number;
  altitude_m?: number;
  label?: string;
  source?: "gps" | "network" | "manual" | "config" | "inferred";
  captured_at?: string;
  [key: string]: unknown;
}

export interface AkousmaCapture {
  direction?: "past" | "future" | "live";
  seconds?: number;
  trigger?: string;
  armed_at?: string;
  triggered_at?: string;
  [key: string]: unknown;
}

export interface AkousmaCovenantWithheld {
  rule?: string;
  subject?: string;
  count?: number;
  [key: string]: unknown;
}

export interface AkousmaCovenant {
  id: string;
  name?: string;
  version?: string;
  contract?: string;
  sha256?: string;
  extends?: string[];
  rules_applied?: string[];
  withheld?: AkousmaCovenantWithheld[];
  commitments?: number;
  note?: string;
  [key: string]: unknown;
}

export type AuditumClaimCategory =
  | "heard"
  | "measured"
  | "inferred"
  | "interpreted"
  | "speculative"
  | "undetermined";

export interface AuditumListening {
  listening_id: string;
  listener_id: string;
  listener_type: "human" | "agent" | "hybrid" | "community" | "institution" | "sensor" | "habitat" | "other_animal" | "ensemble" | "other";
  created_at: string;
  report_namespace: string;
  contract: string;
  context_ref?: string | null;
  apparatus_ref?: string | null;
  claim_set_ref?: string | null;
  covenant_ref?: string | null;
  route?: string[];
  listening_pass_ref?: string | null;
  listening_provenance_ref?: string | null;
  route_decision_refs?: string[];
  influenced_by?: Array<{ listening_id: string; effect: string }>;
  note?: string | null;
}

export interface AuditumDisagreement {
  id: string;
  subject: string;
  listening_ids: string[];
  positions: Array<{
    listening_id: string;
    statement: string;
    claim_category?: AuditumClaimCategory;
  }>;
  status: "preserved" | "resolved" | "undetermined";
  resolution_note?: string | null;
}

export interface AuditumHonestAbsence {
  id: string;
  kind: "unavailable" | "withheld" | "refused" | "not_retained" | "forgotten";
  subject: string;
  attributed_to: string;
  listening_id?: string | null;
  rule?: string | null;
  count?: number | null;
  note?: string | null;
}

export interface AuditumAuthority {
  mode: "observe_only" | "recommend" | "request" | "execute_scoped";
  scopes: string[];
  granted_by?: string | null;
  expires_at?: string | null;
  requires_confirmation: boolean;
  reversible?: boolean | null;
}

export interface AuditumAction {
  action_id: string;
  proposal: string;
  status: "proposed" | "authorized" | "refused" | "executed" | "failed" | "reverted";
  authority: AuditumAuthority;
  receipt?: {
    created_at: string;
    actor: string;
    result?: string | null;
    recovery?: string | null;
  };
}

export interface AuditumRevision {
  revision_id: string;
  revises_akousma_id: string;
  reason: string;
  changes: string[];
  created_at: string;
}

export interface AuditumRouteDecision {
  decision_id: string;
  gate: "input" | "capture" | "inference" | "memory" | "output" | "disclosure" | "retention" | "action";
  outcome: "proceed" | "pause" | "defer" | "abstain" | "refuse" | "withhold" | "forget" | "do_not_act";
  subject: string;
  reason: string;
  decided_at: string;
  listening_id?: string | null;
  producer_contract?: string | null;
  producer_decision_ref?: string | null;
  authority: {
    mode: "observe_only" | "recommend" | "request" | "execute_scoped";
    actor: string;
    covenant_ref?: string | null;
    granted_by?: string | null;
    requires_confirmation: boolean;
    reversible: boolean;
  };
  receipt?: { created_at: string; actor: string; result?: string | null; recovery?: string | null };
  note?: string | null;
}

export interface AuditumEnsemble {
  id: string;
  kind: "plural_listening" | "ear_swarm";
  listening_ids: string[];
  influence_edges: Array<{ from_listening_id: string; to_listening_id: string; effect: string }>;
  permissions_preserved: boolean;
  disagreements_preserved: boolean;
  dissolution_rule: string;
}

export interface Auditum {
  contract: "earworm/auditum/v1" | "earworm/auditum/v2";
  listenings: AuditumListening[];
  disagreements: AuditumDisagreement[];
  honest_absences: AuditumHonestAbsence[];
  actions: AuditumAction[];
  route_decisions?: AuditumRouteDecision[];
  ensemble?: AuditumEnsemble;
  revision?: AuditumRevision;
}

export interface Akousma {
  akousma_id: string;
  schema_version: string;
  created_at: string;
  session_id?: string;
  audio?: AkousmaAudio;
  subject?: string;
  provenance: AkousmaProvenance;
  listening?: Record<string, unknown>;
  lineage: AkousmaLineage;
  tags?: string[];
  annotations?: Record<string, unknown>;
  extensions?: Record<string, unknown>;
  summary?: string;
  location?: AkousmaLocation;
  capture?: AkousmaCapture;
  covenant?: AkousmaCovenant;
  auditum?: Auditum;
  /** Spec v1.6: the record is open — unknown top-level fields are preserved. */
  [key: string]: unknown;
}

export function newAkousmaId(prefix?: string): string;

export function createAkousma(input: {
  audio?: AkousmaAudio;
  originatingApp: string;
  sourceType?: AkousmaProvenance["source_type"];
  origin?: AkousmaProvenance["origin"];
  listening?: Record<string, unknown>;
  parentAkousmaIds?: string[];
  operation?: string | null;
  prompt?: string | null;
  model?: string | null;
  params?: Record<string, unknown> | null;
  relations?: AkousmaRelation[] | null;
  tags?: string[];
  extensions?: Record<string, unknown>;
  sessionId?: string | null;
  summary?: string | null;
  location?: AkousmaLocation | null;
  capture?: AkousmaCapture | null;
  covenant?: AkousmaCovenant | null;
  auditum?: Auditum | null;
  subject?: string | null;
}): Akousma;

export function createAuditum(input: {
  listenings?: AuditumListening[];
  disagreements?: AuditumDisagreement[];
  honestAbsences?: AuditumHonestAbsence[];
  actions?: AuditumAction[];
  routeDecisions: AuditumRouteDecision[];
  ensemble?: AuditumEnsemble | null;
  revision?: AuditumRevision | null;
}): Auditum;

export function createRouteDecision(input: {
  decisionId: string;
  gate: AuditumRouteDecision["gate"];
  outcome: AuditumRouteDecision["outcome"];
  subject: string;
  reason: string;
  actor: string;
  decidedAt?: string | null;
  authorityMode?: AuditumRouteDecision["authority"]["mode"];
  listeningId?: string | null;
  producerContract?: string | null;
  producerDecisionRef?: string | null;
  covenantRef?: string | null;
  grantedBy?: string | null;
  requiresConfirmation?: boolean;
  reversible?: boolean;
  note?: string | null;
}): AuditumRouteDecision;

export function akousmaRelation(
  type: AkousmaRelationType,
  targetAkousmaId: string,
  note?: string | null
): AkousmaRelation;

export function addListening(
  record: Akousma,
  namespace: string,
  payload: Record<string, unknown>,
  options?: { contract?: string | null; summary?: string | null }
): Akousma;

export function listenerTypes(record: Akousma | unknown): AuditumListening["listener_type"][];

export function recordClass(record: Akousma | unknown): AkousmaRecordClass;

export function revisionOf(record: Akousma | unknown): string | null;

export function akousmaShapeErrors(record: unknown): string[];

export function germImportUrl(
  baseUrl: string,
  akousmaId: string,
  mode?: "sound" | "prompt" | "lineage"
): string;

/** Opt-in companion contract; does not change akousma 1.6 or auditum/v2. */
export const LISTENING_ACCESS_CONTRACT: "earworm/listening-access/v1";
export type QualifiedDeclaration<T> = ({ status: "known" } & T) | {
  status: "unknown" | "withheld" | "unavailable" | "not_applicable";
  reason: string;
};
export interface FrequencyBand { lower: number; upper: number }
export interface ListeningAccess {
  contract: typeof LISTENING_ACCESS_CONTRACT;
  declaration_id: string;
  subject_ref: string;
  capture: QualifiedDeclaration<{ apparatus_ref: string; supported_band_hz: FrequencyBand; evidence_refs: string[] }>;
  sampled_representation: QualifiedDeclaration<{ representation_ref: string; sample_rate_hz: number; channels: number; retained_band_hz: FrequencyBand; evidence_refs: string[] }>;
  model_input: QualifiedDeclaration<{
    model_ref: string; representation_ref: string; sample_rate_hz: number; channels: number; blind_spots: string[];
    effective_band_hz: FrequencyBand; window_s: { start: number; end: number };
    preprocessing_refs: string[]; evidence_refs: string[];
  }>;
  human_access: QualifiedDeclaration<{
    listener_ref: string; chain_refs: string[]; conditions: string; rendering_refs: string[];
    access_modes: ("acoustic" | "visual" | "tactile" | "textual" | "other")[]; evidence_refs: string[];
  }>[];
}
export function listeningAccessErrors(value: unknown): string[];
export function assertSupportedContracts(required: string[], supported: string[]): void;
export interface ListeningPassAdapterInput {
  passes: (Record<string, unknown> & {
    id: string; listener_id: string; started_at: string; route: string[]; decision_refs: string[];
    influenced_by: { pass_id: string; effect: string }[]; revision_of?: string | null;
  })[];
  participants: (Record<string, unknown> & { id: string; type: AuditumListening["listener_type"] })[];
  bindings: { pass_id: string; listening_id: string; report_namespace: string; contract: string }[];
  ensemble?: (Record<string, unknown> & {
    id: string; kind: "plural_listening" | "ear_swarm"; participant_ids: string[];
    listening_pass_ids: string[]; influence_edges: { from_pass_id: string; to_pass_id: string; effect: string }[];
    permissions_preserved: boolean; disagreements_preserved: boolean; dissolution_rule: string;
  }) | null;
}
export function adaptListeningPasses(input: ListeningPassAdapterInput): {
  listenings: AuditumListening[];
  ensemble: AuditumEnsemble | null;
  pass_to_listening: Record<string, string>;
  source: { passes: ListeningPassAdapterInput["passes"]; participants: ListeningPassAdapterInput["participants"]; ensemble: ListeningPassAdapterInput["ensemble"] };
};

export const LISTENING_CONTEXT_CONTRACT: "earworm/listening-context/v1";
export type ClaimValidity = { status: "expires"; issued_at: string; expires_at: string }
  | { status: "no_expiry"; issued_at: string; reason: string }
  | { status: "unknown"; reason: string };
export type ClaimRetention = { status: "review_after"; review_after: string; policy_ref: string }
  | { status: "policy"; policy_ref: string } | { status: "unknown"; reason: string };
export interface ListeningClaimLifetime {
  claim_ref: string; listening_ref: string; validity: ClaimValidity; retention: ClaimRetention;
}
export interface ListeningRendering {
  rendering_id: string; source_ref: string; output_ref: string; transformation_ref: string;
  author_ref: string; kind: "transformation" | "interpretation"; media_type: string;
  access: QualifiedDeclaration<{ value: "public" | "restricted" | "private" }>;
}
export interface ListeningContext {
  contract: typeof LISTENING_CONTEXT_CONTRACT;
  access_declarations?: ListeningAccess[];
  contexts: {
    listening_ref: string; subject_ref: string;
    recipients: { id: string; type: AuditumListening["listener_type"] }[];
    access_declaration_ref: string;
    report: {
      ref: string; contract: string; format: string;
      readability: QualifiedDeclaration<{ value: "machine_readable" | "human_readable" | "both" }>;
      human_rendering: { status: "available"; rendering_refs: string[] }
        | { status: "none" | "unknown" | "withheld" | "unavailable"; reason: string };
    };
    renderings: ListeningRendering[];
  }[];
  claims: ListeningClaimLifetime[];
}
export function listeningContextErrors(value: unknown, record: unknown): string[];
export function claimValidityAt(claim: ListeningClaimLifetime, now: string): "current" | "expired" | "not_yet_valid" | "unknown";
export function claimRetentionAt(claim: ListeningClaimLifetime, now: string): "policy_required" | "review_due" | "review_not_due";

export const NEXT_AKOUSMA_SCHEMA_VERSION: "1.7.0";
export const NEXT_AUDITUM_CONTRACT: "earworm/auditum/v3";
export const RECORD_EVOLUTION_CONTRACT: "earworm/akousma/v1.7";
export type RelationReview = { status: "unreviewed" }
  | { status: "accepted" | "rejected" | "contested"; actor_ref: string; reason: string };
export interface SimilarityCriterion {
  descriptor_refs?: {record_ref: string; descriptor_ref: string}[];
  criterion_id: string; feature: string; unit: string; method_ref: string; method_revision: string;
  input_refs: string[]; normalization: string;
  score: { status: "known"; value: number; policy: string }
    | { status: "unknown" | "unavailable" | "not_applicable"; reason: string };
}
export interface EvolutionRelation {
  contract: "earworm/relations/v1"; relation_id: string;
  type: "report_of" | "research_for" | "decision_on" | "observed_from" | "mapped_from" | "similar_by";
  target_akousma_id: string; declared_by: string; evidence_refs: string[];
  epistemic_status: "reported" | "measured" | "inferred" | "interpreted" | "undetermined";
  review: RelationReview; criterion?: SimilarityCriterion;
}
export interface AuditumAppeal {
  contract: "earworm/appeal/v1"; appeal_id: string; recorded_by: string; subject_refs: string[];
  reason: string; status: "unreviewed" | "open" | "under_review" | "resolved" | "withdrawn";
  evidence_refs: string[]; resolution?: { decision_ref: string; reason: string };
  legacy_source?: { record_ref: string; path: "/extensions/oida/appeal"; payload: unknown };
}
export type NextAuditum = Omit<Auditum, "contract"> & { contract: "earworm/auditum/v3"; appeal?: AuditumAppeal };
export type NextAkousma = Omit<Akousma, "schema_version" | "auditum" | "lineage"> & {
  schema_version: "1.7.0"; auditum?: NextAuditum;
  record_kind?: "research_proposal" | "generation_decision" | "observation_account" | "transformation_graph";
  lineage: Omit<AkousmaLineage, "relations"> & { relations?: (AkousmaRelation | EvolutionRelation)[] };
};
export interface AppealPromotionOptions {
  supported_contracts: string[]; akousma_id: string; revision_id: string; created_at: string;
  appeal_id: string; recorded_by: string; reason: string; subject_refs: string[];
}
export function nextRecordErrors(record: unknown): string[];
export function nextRecordReferenceErrors(record: unknown, records: unknown[]): string[];
export function promoteLegacyAppeal(record: Akousma | NextAkousma, options: AppealPromotionOptions): NextAkousma;

export const OBSERVATION_ACCOUNT_CONTRACT: "earworm/observation-account/v1";
export const MATTER_CONTEXT_CONTRACT: "earworm/matter-context/v1";
export interface MatterContext {
  contract: "earworm/matter-context/v1"; context_id: string; vocabulary: "masa/0.2.0";
  source_record_ref: string; subject_ref: string; registers: string[]; scales: string[];
  source_modality: QualifiedDeclaration<{value: "acoustic" | "non_acoustic" | "mixed"; evidence_refs: string[]}>;
  representation: QualifiedDeclaration<{kind: "structured_observation"; observation_ref: string}>;
  access_declaration_ref: string;
  temporal_scope: QualifiedDeclaration<{
    domain: "reported_scope" | "mathematical_construction" | "sampled_representation" | "physical_observation";
    window_s: {start: number; end: number}; resolution_s: number;
    sample_rate_hz: QualifiedDeclaration<{value: number}>; evidence_refs: string[];
  }>;
}
export interface ObservationAccountOptions {
  supported_contracts: string[]; akousma_id: string; created_at: string; originating_app: string;
  listening_id: string; matter_context_id: string; route_decision: AuditumRouteDecision;
  access: ListeningAccess; source_modality: MatterContext["source_modality"];
  representation: MatterContext["representation"]; temporal_scope: MatterContext["temporal_scope"];
}
export function matterContextErrors(value: unknown, source: unknown, access: unknown): string[];
export function observationAccountErrors(record: unknown, validateMapping: (mapping: unknown) => string[]): string[];
export function createObservationAccount(mapping: unknown, options: ObservationAccountOptions, validateMapping: (mapping: unknown) => string[]): NextAkousma;

export const MEASUREMENT_SET_CONTRACT: "earworm/measurement-set/v1";
export const AGENT_SECTOR_CONTRACT: "earworm/agent-sector/v1";
export interface MeasurementDescriptor {
  descriptor_id: string; source_record_ref: string; measurement_ref: string;
  feature: "spectral_centroid" | "band_energy" | "level" | "duration";
  reference_basis: "frequency" | "digital_energy" | "digital_full_scale" | "perceptual_loudness" | "sound_pressure" | "time";
  band_hz: {status: "known"; lower: number; upper: number} | {status: "unknown" | "not_applicable"; reason: string};
  declared_by: string; mapping_reason: string;
}
export interface MeasurementSet {
  contract: "earworm/measurement-set/v1";
  sources: {record_ref: string; record: Record<string, unknown>}[];
  descriptors: MeasurementDescriptor[];
}
export interface AgentSectorEntry {
  sector_id: string; listening_ref: string; subject_ref: string; access_declaration_ref: string;
  source_kind: "acoustic_signal" | "non_acoustic_observation" | "structured_report";
  basis: "retained_measurement" | "retained_observation" | "interpretation";
  measurement_refs: string[]; claim_refs: string[]; renderings: string[];
}
export function measurementSetErrors(value: unknown, validateMasa: (record: unknown) => string[]): string[];
export function createMeasurementSet(sources: Record<string, unknown>[], descriptors: MeasurementDescriptor[], validateMasa: (record: unknown) => string[], supportedContracts: string[]): MeasurementSet;
export function agentSectorView(record: NextAkousma, sectorId: string): {entry: AgentSectorEntry; access: ListeningAccess; renderings: ListeningRendering[]; measurements: {descriptor: MeasurementDescriptor; measurement: Record<string, unknown>}[]};
export interface DescriptorComparisonOptions {
  supported_contracts: string[]; relation_id: string; criterion_id: string; declared_by: string;
  source_descriptor_ref: string; target_descriptor_ref: string;
}
export function compareMeasurementDescriptors(source: NextAkousma, target: NextAkousma, options: DescriptorComparisonOptions): EvolutionRelation;

/** Unreleased local views require host permission; they grant no disclosure rights. */
export const AUDITUM_VIEW_CONTRACT: "earworm/auditum-view/v1";
export const FORGETTING_RECEIPT_CONTRACT: "earworm/forgetting-receipt/v1";
export interface ForgettingReceiptView {
  contract: typeof FORGETTING_RECEIPT_CONTRACT;
  receipt_id: string;
  akousma_id: string;
  created_at: string;
  record_deleted: true;
  audio_deletion_requested: boolean;
  audio_deleted: boolean;
  shared_audio_preserved: boolean;
}
export type AuditumReferenceView = { record_ref: string } & (
  { state: "available" | "unavailable" | "withheld" } |
  { state: "forgotten"; receipt: ForgettingReceiptView }
);
export type AuditumView = AuditumReferenceView & {
  contract: typeof AUDITUM_VIEW_CONTRACT;
  auditum?: Record<string, unknown> | null;
  references?: AuditumReferenceView[];
};
export function forgettingReceiptView(receipt: unknown, recordId: string): ForgettingReceiptView;
export function auditumView(recordId: string, options: {
  readRecord: (id: string) => unknown | null;
  readReceipt: (id: string) => unknown | null;
  canRead: (id: string) => boolean;
  supported_contracts: string[];
}): AuditumView;

export const TRANSFORMATION_GRAPH_CONTRACT: "earworm/transformation-graph/v1";
export interface TransformationPatchNode { node_id: string; representation_ref: string }
export interface TransformationGraph {
  contract: typeof TRANSFORMATION_GRAPH_CONTRACT;
  graph_id: string;
  revision: number;
  authored_by: string;
  scope: "completed_representation_lineage";
  source_record: Record<string, unknown>;
  nodes: TransformationPatchNode[];
  edges: { relation_ref: string; operation_ref: string; from_node: string; to_node: string }[];
  operation_refs: string[];
}
/** Inject the actual MASA validator and exported versioned lineage direction registry. */
export interface TransformationMasaAdapter {
  validateMasa: (value: unknown) => string[];
  lineageDirections: Readonly<Record<string, "subject-is-descendant" | "object-is-descendant">>;
}
export function createTransformationGraph(record: unknown, options: {
  graph_id: string;
  revision: number;
  authored_by: string;
  nodes: TransformationPatchNode[];
  supported_contracts: string[];
}, masa: TransformationMasaAdapter): TransformationGraph;
export function transformationGraphErrors(graph: unknown, masa: TransformationMasaAdapter): string[];

export const TRANSPOSITION_RECIPE_CONTRACT: "earworm/transposition-recipe/v1";
export function transpositionRecipeErrors(source: unknown): string[];
export function transformationGraphBindingErrors(graph: unknown): string[];
export function graphRevisionErrors(record: NextAkousma, previous: NextAkousma): string[];
export interface GraphRecordOptions { created_at: string; originating_app: string; supported_contracts: string[] }
export function createGraphRecord(graph: TransformationGraph, options: GraphRecordOptions, masa: TransformationMasaAdapter): NextAkousma;
export interface GraphRevisionOptions {
  akousma_id: string; revision_id: string; created_at: string; reason: string;
  authored_by: string; nodes: TransformationPatchNode[]; supported_contracts: string[];
}
export function reviseGraphRecord(record: NextAkousma, options: GraphRevisionOptions, masa: TransformationMasaAdapter): NextAkousma;

export function bundleManifestErrors(manifest: unknown): string[];

export declare function modelEcologyErrors(name: "embedding-space" | "analysis-evidence" | "model-deployment", value: unknown): string[];

export function spectralBundleErrors(bundle: unknown, options?: {resolveObject?: (ref: string) => unknown}): string[];
export function record18Errors(record: unknown, options?: {validateNative?: (value: unknown) => string[]; resolveObject?: (ref: string) => unknown}): string[];
export function admitRecord18(record: unknown, options: {supportedVersions: string[]; validateNative?: (value: unknown) => string[]; resolveObject?: (ref: string) => unknown; resolveRepresentation?: (ref: string) => unknown}): unknown;
