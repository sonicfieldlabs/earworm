/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

import {
  InMemoryEventStore,
  JsonlEventStore,
  commitAutomation,
  createSession,
  createSnapshot,
  emitModulationIntent,
  exportManifest,
  ingestAlignment,
  ingestAnalysis,
  ingestGeneratedAsset,
  ingestGenerationRequest,
  ingestPrompt,
  ingestSignalPacket,
  queryContext,
  recordAgentAction,
  revertAutomation
} from "@earworm/core";

export class EarwormClient {
  constructor({ session, store } = {}) {
    if (!session && !store) {
      throw new Error("EarwormClient requires a session or store");
    }
    this.store = store ?? new InMemoryEventStore(session);
    this.session_id = this.store.session.session_id;
  }

  static create({ session_id, app_id, policy, created_at, assets, provenance }) {
    const session = createSession({ session_id, app_id, policy, created_at, assets, provenance });
    return new EarwormClient({ session });
  }

  get session() {
    return this.store.session;
  }

  get events() {
    return this.store.events;
  }

  append(event) {
    return this.store.append(event);
  }

  ingestPrompt(input) {
    return ingestPrompt(this.store, input);
  }

  ingestGenerationRequest(input) {
    return ingestGenerationRequest(this.store, input);
  }

  ingestGeneratedAsset(input) {
    return ingestGeneratedAsset(this.store, input);
  }

  ingestAlignment(input) {
    return ingestAlignment(this.store, input);
  }

  ingestSignalPacket(input) {
    return ingestSignalPacket(this.store, input);
  }

  ingestAnalysis(input) {
    return ingestAnalysis(this.store, input);
  }

  emitModulationIntent(input) {
    return emitModulationIntent(this.store, input);
  }

  commitAutomation(input) {
    return commitAutomation(this.store, input);
  }

  revertAutomation(laneEventId, input) {
    return revertAutomation(this.store, laneEventId, input);
  }

  recordAgentAction(input) {
    return recordAgentAction(this.store, input);
  }

  createSnapshot(input) {
    return createSnapshot(this.store, input);
  }

  queryContext(selector) {
    return queryContext(this.store.session, this.store.events, selector);
  }

  exportManifest(scope) {
    return exportManifest(this.store.session, this.store.events, scope);
  }
}

export {
  InMemoryEventStore,
  JsonlEventStore,
  createSession,
  queryContext,
  exportManifest,
  revertAutomation
} from "@earworm/core";

export {
  AKOUSMA_SCHEMA_VERSION,
  AKOUSMA_SOURCE_TYPES,
  AKOUSMA_ORIGINS,
  AKOUSMA_RELATION_TYPES,
  AKOUSMA_PIPELINE_EFFECTS,
  AKOUSMA_LOCATION_SOURCES,
  AKOUSMA_CAPTURE_DIRECTIONS,
  AUDITUM_CONTRACT,
  AUDITUM_LISTENER_TYPES,
  AUDITUM_ABSENCE_KINDS,
  AUDITUM_DISAGREEMENT_STATUSES,
  AUDITUM_ACTION_STATUSES,
  GERM_IMPORT_MODES,
  newAkousmaId,
  createAkousma,
  createAuditum,
  akousmaRelation,
  addListening,
  akousmaShapeErrors,
  germImportUrl
} from "./akousma.js";
