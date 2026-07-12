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
export const GERM_IMPORT_MODES: readonly ["sound", "prompt", "lineage"];

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

export interface Akousma {
  akousma_id: string;
  schema_version: string;
  created_at: string;
  session_id?: string;
  audio: AkousmaAudio;
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
  /** Spec v1.2: the record is open — unknown top-level fields are preserved. */
  [key: string]: unknown;
}

export function newAkousmaId(prefix?: string): string;

export function createAkousma(input: {
  audio: AkousmaAudio;
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
}): Akousma;

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

export function akousmaShapeErrors(record: unknown): string[];

export function germImportUrl(
  baseUrl: string,
  akousmaId: string,
  mode?: "sound" | "prompt" | "lineage"
): string;
