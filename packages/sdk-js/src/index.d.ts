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
