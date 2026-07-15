/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

import { createHash } from "node:crypto";
import { mkdir, readFile, rename, writeFile } from "node:fs/promises";
import { dirname } from "node:path";

export type EventActor = "user" | "agent" | "system" | "provider";

export type EventType =
  | "prompt.ingested"
  | "generation.requested"
  | "audio.generated"
  | "signal.packet.ingested"
  | "alignment.ingested"
  | "analysis.frame"
  | "dsp.parameter.changed"
  | "agent.action.proposed"
  | "agent.action.applied"
  | "automation.committed"
  | "automation.reverted"
  | "render.created"
  | "snapshot.created";

export type JsonObject = Record<string, unknown>;

export type RetentionPolicy = {
  mode: "ephemeral" | "project_lifetime" | "expires_at" | "custom";
  expires_at?: string;
  local_only: boolean;
  redaction: {
    sensitive_fields: string[];
    agent_safe_omissions: string[];
  };
};

export type EarwormTime = {
  wall_clock: string;
  project_seconds?: number;
  asset_seconds?: number;
  sample_index?: number;
  char_range?: [number, number];
  word_range?: [number, number];
};

export type EarwormEvent = {
  event_id: string;
  session_id: string;
  type: EventType;
  time: EarwormTime;
  source: {
    actor: EventActor;
    node_id?: string;
  };
  payload: JsonObject;
  confidence?: number;
  reversible: boolean;
  parent_event_ids: string[];
  provenance_id?: string;
  prev_event_hash?: string;
  event_hash?: string;
};

export type AssetRef = {
  asset_id: string;
  type?: string;
  uri?: string;
  duration_seconds?: number;
  sample_rate?: number;
  channels?: number;
  provenance_id?: string;
  [key: string]: unknown;
};

export type ProvenanceRecord = {
  provenance_id: string;
  source_type: "generated" | "recorded" | "imported" | "cloned" | "designed" | "unknown";
  provider?: string;
  model_id?: string;
  voice_id?: string;
  seed?: number;
  request_hash?: string;
  asset_hash?: string;
  consent_status: "owned" | "licensed" | "public_domain" | "unknown" | "restricted";
  usage_constraints: string[];
  created_at: string;
};

export type EarwormSession = {
  session_id: string;
  app_id: string;
  created_at: string;
  policy: RetentionPolicy;
  assets: AssetRef[];
  events: EarwormEvent[];
  provenance: ProvenanceRecord[];
  views: EarwormViews;
  indexes: {
    by_time: boolean;
    by_asset: boolean;
    by_node: boolean;
    by_text: boolean;
  };
};

export type EarwormViews = {
  current_state: JsonObject;
  summaries: JsonObject[];
};

export type ContextSelector = {
  time_range?: { start: number; end: number };
  include?: Array<keyof typeof includeTypeGroups>;
  asset_id?: string;
  node_id?: string;
  event_types?: EventType[];
  summarization?: "compact" | "full" | "agent_safe";
  max_tokens?: number;
  time_domain?: "asset" | "project" | "wall_clock";
};

export type ContextBundle = {
  session_id: string;
  selector: ContextSelector;
  events: EarwormEvent[];
  assets: AssetRef[];
  provenance: ProvenanceRecord[];
  summaries: JsonObject[];
};

export type ModulationIntent = {
  intent_id: string;
  target: string;
  reason: "prompt_trait" | "audio_tag" | "analysis_feature" | "user_feedback" | "agent_evaluation";
  source_refs: string[];
  mapping: {
    type: "linear" | "rule" | "ml" | "manual";
    parameters: JsonObject;
  };
  constraints: {
    min?: number;
    max?: number;
    smoothing_ms?: number;
    protect_intelligibility?: boolean;
  };
  output_lane_ref?: string;
  confidence: number;
};

export type AutomationLane = {
  lane_id: string;
  target: string;
  unit: string;
  points: Array<{
    time: number;
    value: number;
    curve?: "step" | "linear" | "ease";
  }>;
  source_intent_id: string;
  reversible: boolean;
  rollback_lane_ref?: string;
};

export type SignalPacket = {
  packet_id: string;
  signal_type: "audio" | "midi" | "text" | "control" | "video" | "image";
  asset_ref?: string;
  segment_id?: string;
  time_range: { start: number; end: number; unit: "seconds" | "samples" | "frames" };
  context_refs: string[];
  features_ref?: string;
  feature_stream_ref?: string;
  provenance_id?: string;
  tags: string[];
};

export type AnalysisFrame = {
  frame_id: string;
  asset_ref: string;
  time_range: { start: number; end: number; unit: "seconds" };
  features: JsonObject;
  confidence?: number;
};

export type FeatureStreamRef = {
  features_ref: string;
  asset_ref: string;
  format: "json_frames" | "binary_sidecar" | "external";
  uri?: string;
  time_range: { start: number; end: number; unit: "seconds" | "samples" };
  sample_rate_hz?: number;
  feature_names: string[];
};

export type Indexes = {
  byId: Map<string, EarwormEvent>;
  byType: Map<EventType, EarwormEvent[]>;
  byAsset: Map<string, EarwormEvent[]>;
  byNode: Map<string, EarwormEvent[]>;
  byTime: EarwormEvent[];
  byText: Map<string, EarwormEvent[]>;
};

export type EventStore = {
  readonly session: EarwormSession;
  readonly events: readonly EarwormEvent[];
  append(event: EarwormEvent): string;
  registerAsset(asset: AssetRef): void;
  registerProvenance(record: ProvenanceRecord): void;
};

export type ExportManifest = {
  manifest_id: string;
  session_id: string;
  app_id: string;
  created_at: string;
  scope: ManifestScope;
  assets: AssetRef[];
  events: EarwormEvent[];
  provenance: ProvenanceRecord[];
  policy: RetentionPolicy;
  views: EarwormViews;
  audit: ManifestAudit;
};

export type ManifestAudit = {
  asset_count: number;
  event_count: number;
  provenance_count: number;
  rights_status?: "complete" | "incomplete" | "restricted" | "unknown";
  warnings: string[];
};

export type ManifestScope = {
  manifest_id?: string;
  asset_id?: string;
  event_types?: EventType[];
  require_complete_provenance?: boolean;
  created_at?: string;
};

type EventDraft = {
  event_id: string;
  type: EventType;
  source: EarwormEvent["source"];
  payload: JsonObject;
  confidence?: number | undefined;
  reversible: boolean;
  parent_event_ids: string[];
  provenance_id?: string | undefined;
  time?: Partial<EarwormTime>;
};

const includeTypeGroups = {
  prompt: new Set<EventType>(["prompt.ingested"]),
  generation: new Set<EventType>(["generation.requested", "audio.generated"]),
  signal: new Set<EventType>(["signal.packet.ingested"]),
  alignment: new Set<EventType>(["alignment.ingested"]),
  analysis: new Set<EventType>(["analysis.frame"]),
  automation: new Set<EventType>(["automation.committed", "automation.reverted", "dsp.parameter.changed"]),
  provenance: new Set<EventType>([]),
  agent_actions: new Set<EventType>(["agent.action.proposed", "agent.action.applied"]),
  renders: new Set<EventType>(["render.created"])
};

export function createSession({
  session_id,
  app_id,
  created_at = new Date().toISOString(),
  policy,
  assets = [],
  provenance = []
}: {
  session_id: string;
  app_id: string;
  created_at?: string;
  policy: RetentionPolicy;
  assets?: AssetRef[];
  provenance?: ProvenanceRecord[];
}): EarwormSession {
  return {
    session_id,
    app_id,
    created_at,
    policy,
    assets,
    events: [],
    provenance,
    views: {
      current_state: {},
      summaries: []
    },
    indexes: {
      by_time: true,
      by_asset: true,
      by_node: true,
      by_text: true
    }
  };
}

export class InMemoryEventStore implements EventStore {
  #session: EarwormSession;
  #events: EarwormEvent[];
  indexes: Indexes;

  constructor(session: EarwormSession) {
    this.#session = cloneSessionState(session, []);
    this.#events = [];
    this.indexes = buildIndexes(this.#events);
    for (const event of session.events ?? []) {
      this.append(event);
    }
  }

  get session(): EarwormSession {
    return deepFreezeCopy(this.#session);
  }

  get events(): readonly EarwormEvent[] {
    return Object.freeze([...this.#events]);
  }

  append(event: EarwormEvent): string {
    const appendable = prepareEventForAppend(this.#session, this.#events, event);
    this.#events.push(appendable);
    this.syncSession();
    return appendable.event_id;
  }

  registerAsset(asset: AssetRef): void {
    const existing = this.#session.assets.find((candidate) => candidate.asset_id === asset.asset_id);
    if (existing) {
      assertMatchingRegistration("asset", asset.asset_id, existing, asset);
      return;
    }
    this.#session.assets = [...this.#session.assets, deepFreezeCopy(asset)];
  }

  registerProvenance(record: ProvenanceRecord): void {
    const existing = this.#session.provenance.find((candidate) => candidate.provenance_id === record.provenance_id);
    if (existing) {
      assertMatchingRegistration("provenance record", record.provenance_id, existing, record);
      return;
    }
    this.#session.provenance = [...this.#session.provenance, deepFreezeCopy(record)];
  }

  private syncSession(): void {
    this.indexes = buildIndexes(this.#events);
    this.#session = {
      ...this.#session,
      events: this.#events,
      views: rebuildCurrentState(this.#session, this.#events)
    };
  }

  byType(type: EventType): EarwormEvent[] {
    return this.indexes.byType.get(type) ?? [];
  }

  byAsset(assetId: string): EarwormEvent[] {
    return this.indexes.byAsset.get(assetId) ?? [];
  }

  byNode(nodeId: string): EarwormEvent[] {
    return this.indexes.byNode.get(nodeId) ?? [];
  }

  byTimeRange(start: number, end: number): EarwormEvent[] {
    return this.indexes.byTime.filter((event) => {
      const value = eventTimeValue(event);
      return typeof value === "number" && value >= start && value <= end;
    });
  }

  byTextRange(start: number, end: number): EarwormEvent[] {
    const events: EarwormEvent[] = [];
    for (const event of this.indexes.byText.values()) {
      events.push(...event.filter((candidate) => overlapsTextRange(candidate, start, end)));
    }
    return uniqueEvents(events);
  }
}

export class JsonlEventStore implements EventStore {
  #session: EarwormSession;
  #events: EarwormEvent[];
  indexes: Indexes;
  readonly path: string;

  private constructor(path: string, session: EarwormSession, events: EarwormEvent[]) {
    this.path = path;
    this.#session = cloneSessionState(session, []);
    this.#events = [];
    this.indexes = buildIndexes(this.#events);
    for (const event of events) {
      this.appendLoadedEvent(event);
    }
  }

  static async create(path: string, session: EarwormSession): Promise<JsonlEventStore> {
    const store = new JsonlEventStore(path, { ...session, events: [] }, []);
    await store.persist();
    return store;
  }

  static async load(path: string, session: EarwormSession): Promise<JsonlEventStore> {
    const text = await readFile(path, "utf8");
    const events = text
      .split("\n")
      .filter(Boolean)
      .map((line) => JSON.parse(line) as EarwormEvent);
    return new JsonlEventStore(path, { ...session, events }, events);
  }

  get session(): EarwormSession {
    return deepFreezeCopy(this.#session);
  }

  get events(): readonly EarwormEvent[] {
    return Object.freeze([...this.#events]);
  }

  append(event: EarwormEvent): string {
    const appendable = prepareEventForAppend(this.#session, this.#events, event);
    this.#events.push(appendable);
    this.syncSession();
    return appendable.event_id;
  }

  registerAsset(asset: AssetRef): void {
    const existing = this.#session.assets.find((candidate) => candidate.asset_id === asset.asset_id);
    if (existing) {
      assertMatchingRegistration("asset", asset.asset_id, existing, asset);
      return;
    }
    this.#session.assets = [...this.#session.assets, deepFreezeCopy(asset)];
  }

  registerProvenance(record: ProvenanceRecord): void {
    const existing = this.#session.provenance.find((candidate) => candidate.provenance_id === record.provenance_id);
    if (existing) {
      assertMatchingRegistration("provenance record", record.provenance_id, existing, record);
      return;
    }
    this.#session.provenance = [...this.#session.provenance, deepFreezeCopy(record)];
  }

  private appendLoadedEvent(event: EarwormEvent): void {
    assertAppendableLoadedEvent(this.#session, this.#events, event);
    this.#events.push(deepFreezeCopy(event));
    this.syncSession();
  }

  private syncSession(): void {
    this.indexes = buildIndexes(this.#events);
    this.#session = {
      ...this.#session,
      events: this.#events,
      views: rebuildCurrentState(this.#session, this.#events)
    };
  }

  async persist(): Promise<void> {
    await mkdir(dirname(this.path), { recursive: true });
    const tmpPath = `${this.path}.tmp`;
    await writeFile(tmpPath, this.#events.map((event) => JSON.stringify(event)).join("\n") + (this.#events.length ? "\n" : ""));
    await rename(tmpPath, this.path);
  }

  async appendAndPersist(event: EarwormEvent): Promise<string> {
    const eventId = this.append(event);
    await this.persist();
    return eventId;
  }

  byType(type: EventType): EarwormEvent[] {
    return this.indexes.byType.get(type) ?? [];
  }

  byAsset(assetId: string): EarwormEvent[] {
    return this.indexes.byAsset.get(assetId) ?? [];
  }

  byNode(nodeId: string): EarwormEvent[] {
    return this.indexes.byNode.get(nodeId) ?? [];
  }

  byTimeRange(start: number, end: number): EarwormEvent[] {
    return this.indexes.byTime.filter((event) => {
      const value = eventTimeValue(event);
      return typeof value === "number" && value >= start && value <= end;
    });
  }

  byTextRange(start: number, end: number): EarwormEvent[] {
    const events: EarwormEvent[] = [];
    for (const event of this.indexes.byText.values()) {
      events.push(...event.filter((candidate) => overlapsTextRange(candidate, start, end)));
    }
    return uniqueEvents(events);
  }
}

export function ingestPrompt(
  store: EventStore,
  { event_id, prompt, metadata = {}, time = {}, source = {} }: {
    event_id: string;
    prompt: string;
    metadata?: JsonObject;
    time?: Partial<EarwormTime>;
    source?: { node_id?: string };
  }
): string {
  return store.append(
    baseEvent(store.session.session_id, {
      event_id,
      type: "prompt.ingested",
      time,
      source: { actor: "user", node_id: source.node_id ?? "earworm.prompt" },
      payload: { prompt, ...metadata },
      reversible: false,
      parent_event_ids: []
    })
  );
}

export function ingestGenerationRequest(
  store: EventStore,
  {
    event_id,
    provider,
    request,
    provenance_id,
    parent_event_ids = [],
    time = {},
    source = {}
  }: {
    event_id: string;
    provider: string;
    request: JsonObject;
    provenance_id?: string;
    parent_event_ids?: string[];
    time?: Partial<EarwormTime>;
    source?: { node_id?: string };
  }
): string {
  return store.append(
    baseEvent(store.session.session_id, {
      event_id,
      type: "generation.requested",
      time,
      source: { actor: "system", node_id: source.node_id ?? "earworm.generation" },
      payload: { provider, ...request },
      reversible: false,
      parent_event_ids,
      provenance_id
    })
  );
}

export function ingestGeneratedAsset(
  store: EventStore,
  {
    event_id,
    asset,
    response_metadata = {},
    provenance,
    parent_event_ids = [],
    time = {},
    source = {}
  }: {
    event_id: string;
    asset: AssetRef;
    response_metadata?: JsonObject;
    provenance?: ProvenanceRecord;
    parent_event_ids?: string[];
    time?: Partial<EarwormTime>;
    source?: { node_id?: string };
  }
): string {
  if (provenance && asset.provenance_id && provenance.provenance_id !== asset.provenance_id) {
    throw new Error(`asset ${asset.asset_id} provenance_id ${asset.provenance_id} does not match record ${provenance.provenance_id}`);
  }

  const event = baseEvent(store.session.session_id, {
    event_id,
    type: "audio.generated",
    time,
    source: { actor: "provider", node_id: source.node_id ?? "earworm.provider" },
    payload: {
      asset_id: asset.asset_id,
      duration_seconds: asset.duration_seconds,
      response_metadata
    },
    reversible: false,
    parent_event_ids,
    provenance_id: asset.provenance_id
  });

  assertAppendableGeneratedAsset(store, event, provenance);
  store.registerAsset(asset);
  if (provenance) {
    store.registerProvenance(provenance);
  }
  return store.append(event);
}

export function ingestSignalPacket(
  store: EventStore,
  {
    event_id,
    packet,
    parent_event_ids = [],
    time = {},
    source = {}
  }: {
    event_id: string;
    packet: SignalPacket;
    parent_event_ids?: string[];
    time?: Partial<EarwormTime>;
    source?: { node_id?: string };
  }
): string {
  return store.append(
    baseEvent(store.session.session_id, {
      event_id,
      type: "signal.packet.ingested",
      time,
      source: { actor: "system", node_id: source.node_id ?? "earworm.signal" },
      payload: { asset_id: packet.asset_ref, packet },
      reversible: false,
      parent_event_ids,
      provenance_id: packet.provenance_id ?? provenanceIdForAsset(store.session, packet.asset_ref)
    })
  );
}

export function ingestAlignment(
  store: EventStore,
  {
    event_id,
    asset_id,
    alignment,
    parent_event_ids = [],
    time = {},
    source = {}
  }: {
    event_id: string;
    asset_id: string;
    alignment: JsonObject & { confidence?: number };
    parent_event_ids?: string[];
    time?: Partial<EarwormTime>;
    source?: { node_id?: string };
  }
): string {
  return store.append(
    baseEvent(store.session.session_id, {
      event_id,
      type: "alignment.ingested",
      time,
      source: { actor: "system", node_id: source.node_id ?? "earworm.alignment" },
      payload: { asset_id, ...alignment },
      confidence: alignment.confidence,
      reversible: false,
      parent_event_ids,
      provenance_id: provenanceIdForAsset(store.session, asset_id)
    })
  );
}

export function ingestAnalysis(
  store: EventStore,
  {
    event_id,
    asset_id,
    frames,
    parent_event_ids = [],
    time = {},
    source = {}
  }: {
    event_id: string;
    asset_id: string;
    frames: AnalysisFrame[];
    parent_event_ids?: string[];
    time?: Partial<EarwormTime>;
    source?: { node_id?: string };
  }
): string {
  return store.append(
    baseEvent(store.session.session_id, {
      event_id,
      type: "analysis.frame",
      time,
      source: { actor: "system", node_id: source.node_id ?? "earworm.analysis" },
      payload: { asset_id, frames: frames.map((frame) => ({ ...frame, asset_ref: frame.asset_ref ?? asset_id })) },
      confidence: averageConfidence(frames),
      reversible: false,
      parent_event_ids,
      provenance_id: provenanceIdForAsset(store.session, asset_id)
    })
  );
}

export function emitModulationIntent(
  store: EventStore,
  {
    event_id,
    intent,
    parent_event_ids = [],
    time = {},
    source = {}
  }: {
    event_id: string;
    intent: ModulationIntent;
    parent_event_ids?: string[];
    time?: Partial<EarwormTime>;
    source?: { node_id?: string };
  }
): string {
  return store.append(
    baseEvent(store.session.session_id, {
      event_id,
      type: "agent.action.proposed",
      time,
      source: { actor: "agent", node_id: source.node_id ?? "earworm.mapper" },
      payload: { intent },
      confidence: intent.confidence,
      reversible: true,
      parent_event_ids
    })
  );
}

export function commitAutomation(
  store: EventStore,
  {
    event_id,
    intent,
    lane,
    parent_event_ids = [],
    time = {},
    source = {}
  }: {
    event_id: string;
    intent: ModulationIntent;
    lane: AutomationLane;
    parent_event_ids?: string[];
    time?: Partial<EarwormTime>;
    source?: { node_id?: string };
  }
): string {
  assertAutomationTraceability(store, intent, lane, parent_event_ids);
  enforceLaneConstraints(intent, lane);
  return store.append(
    baseEvent(store.session.session_id, {
      event_id,
      type: "automation.committed",
      time,
      source: { actor: "agent", node_id: source.node_id ?? "earworm.automation" },
      payload: removeUndefined({
        intent,
        lane,
        asset_ids: assetIdsForSourceRefs(store.events, intent.source_refs)
      }) as JsonObject,
      confidence: intent.confidence,
      reversible: lane.reversible,
      parent_event_ids
    })
  );
}

export function revertAutomation(
  store: EventStore,
  laneEventId: string,
  {
    event_id = `evt_revert_${laneEventId}`,
    parent_event_ids = [laneEventId],
    time = {},
    source = {}
  }: {
    event_id?: string;
    parent_event_ids?: string[];
    time?: Partial<EarwormTime>;
    source?: { node_id?: string };
  } = {}
): string {
  const committed = store.events.find((event) => event.event_id === laneEventId && event.type === "automation.committed");
  if (!committed) {
    throw new Error(`automation event ${laneEventId} not found`);
  }

  const lane = committed.payload.lane;
  if (!isAutomationLane(lane)) {
    throw new Error(`automation event ${laneEventId} does not include a valid lane`);
  }
  if (!lane.reversible) {
    throw new Error(`automation lane ${lane.lane_id} is not reversible`);
  }

  const rollbackLane: AutomationLane = {
    lane_id: lane.rollback_lane_ref ?? `${lane.lane_id}.rollback`,
    target: lane.target,
    unit: lane.unit,
    points: lane.points.map((point) => removeUndefined({
      time: point.time,
      value: 0,
      curve: point.curve
    }) as AutomationLane["points"][number]),
    source_intent_id: lane.source_intent_id,
    reversible: false,
    rollback_lane_ref: lane.lane_id
  };

  return store.append(
    baseEvent(store.session.session_id, {
      event_id,
      type: "automation.reverted",
      time,
      source: { actor: "agent", node_id: source.node_id ?? "earworm.automation" },
      payload: {
        reverts_event_id: laneEventId,
        reverts_lane_id: lane.lane_id,
        lane: rollbackLane
      },
      reversible: false,
      parent_event_ids
    })
  );
}

export function recordAgentAction(
  store: EventStore,
  {
    event_id,
    action,
    parent_event_ids = [],
    time = {},
    source = {}
  }: {
    event_id: string;
    action: JsonObject & { applied?: boolean; confidence?: number; reversible?: boolean };
    parent_event_ids?: string[];
    time?: Partial<EarwormTime>;
    source?: { node_id?: string };
  }
): string {
  return store.append(
    baseEvent(store.session.session_id, {
      event_id,
      type: action.applied ? "agent.action.applied" : "agent.action.proposed",
      time,
      source: { actor: "agent", node_id: source.node_id ?? "earworm.agent" },
      payload: { action },
      confidence: action.confidence,
      reversible: Boolean(action.reversible),
      parent_event_ids
    })
  );
}

export function createSnapshot(
  store: EventStore,
  { event_id, label, time = {}, source = {} }: {
    event_id: string;
    label: string;
    time?: Partial<EarwormTime>;
    source?: { node_id?: string };
  }
): string {
  return store.append(
    baseEvent(store.session.session_id, {
      event_id,
      type: "snapshot.created",
      time,
      source: { actor: "system", node_id: source.node_id ?? "earworm.snapshot" },
      payload: {
        label,
        event_count: store.events.length,
        current_state: rebuildCurrentState(store.session, store.events).current_state
      },
      reversible: false,
      parent_event_ids: store.events.at(-1) ? [store.events.at(-1)!.event_id] : []
    })
  );
}

export function buildIndexes(events: readonly EarwormEvent[]): Indexes {
  const indexes: Indexes = {
    byId: new Map(),
    byType: new Map(),
    byAsset: new Map(),
    byNode: new Map(),
    byTime: [],
    byText: new Map()
  };

  for (const event of events) {
    indexes.byId.set(event.event_id, event);
    appendIndex(indexes.byType, event.type, event);
    if (event.source.node_id) {
      appendIndex(indexes.byNode, event.source.node_id, event);
    }
    indexes.byTime.push(event);
    if (event.time.char_range) {
      appendIndex(indexes.byText, textRangeKey(event.time.char_range), event);
    }
    if (event.time.word_range) {
      appendIndex(indexes.byText, textRangeKey(event.time.word_range), event);
    }
    for (const assetId of assetIdsForEvent(event)) {
      appendIndex(indexes.byAsset, assetId, event);
    }
  }

  indexes.byTime.sort((left, right) => (eventTimeValue(left, "asset") ?? 0) - (eventTimeValue(right, "asset") ?? 0));

  return indexes;
}

export function rebuildCurrentState(_session: EarwormSession, events: readonly EarwormEvent[]): EarwormViews {
  const current_state: JsonObject = {
    event_count: events.length
  };

  for (const event of events) {
    if (event.type === "audio.generated" && typeof event.payload.asset_id === "string") {
      current_state.active_asset_id = event.payload.asset_id;
    }
    if (event.type === "render.created" && typeof event.payload.render_id === "string") {
      current_state.latest_render_id = event.payload.render_id;
    }
  }

  return {
    current_state,
    summaries: _session.views?.summaries ?? []
  };
}

export function queryContext(session: EarwormSession, events: readonly EarwormEvent[], selector: ContextSelector = {}): ContextBundle {
  assertRetentionActive(session.policy);
  const selectedEvents = selectEvents(events, selector);
  const selectedAssetIds = new Set(selectedEvents.flatMap(assetIdsForEvent));
  const selectedProvenanceIds = new Set(
    selectedEvents
      .map((event) => event.provenance_id)
      .filter((id): id is string => Boolean(id))
  );
  if (selector.asset_id) {
    const asset = session.assets.find((candidate) => candidate.asset_id === selector.asset_id);
    if (asset?.provenance_id) {
      selectedProvenanceIds.add(asset.provenance_id);
    }
  }

  return {
    session_id: session.session_id,
    selector: deepFreezeCopy(selector),
    events: applyContextBudget(redactEvents(selectedEvents, session.policy, selector.summarization), selector.max_tokens),
    assets: deepFreezeCopy(session.assets.filter((asset) => selectedAssetIds.has(asset.asset_id) || asset.asset_id === selector.asset_id)),
    provenance: deepFreezeCopy(selectProvenance(session, selector, selectedProvenanceIds)),
    summaries: deepFreezeCopy(session.views?.summaries ?? [])
  };
}

export function exportManifest(session: EarwormSession, events: readonly EarwormEvent[], scope: ManifestScope = {}): ExportManifest {
  assertRetentionActive(session.policy);
  const selector: ContextSelector = {};
  if (scope.asset_id) {
    selector.asset_id = scope.asset_id;
  }
  if (scope.event_types) {
    selector.event_types = scope.event_types;
  }
  const selectedEvents = selectEvents(events, selector);
  const assetIds = new Set(selectedEvents.flatMap(assetIdsForEvent));
  const provenanceIds = new Set(
    selectedEvents
      .map((event) => event.provenance_id)
      .filter((id): id is string => Boolean(id))
  );

  const assets = session.assets.filter((asset) => !scope.asset_id || assetIds.has(asset.asset_id));
  for (const asset of assets) {
    if (asset.provenance_id) {
      provenanceIds.add(asset.provenance_id);
    }
  }
  const provenance = session.provenance.filter((record) => provenanceIds.has(record.provenance_id));
  const audit = createManifestAudit(assets, selectedEvents, provenance);

  if (scope.require_complete_provenance) {
    const missing = assets.filter((asset) => !asset.provenance_id || !provenanceIds.has(asset.provenance_id));
    if (missing.length > 0) {
      throw new Error(`manifest export blocked: missing provenance for ${missing.map((asset) => asset.asset_id).join(", ")}`);
    }
  }

  return {
    manifest_id: scope.manifest_id ?? `manifest_${session.session_id}`,
    session_id: session.session_id,
    app_id: session.app_id,
    created_at: scope.created_at ?? new Date().toISOString(),
    scope,
    assets: deepFreezeCopy(assets),
    events: deepFreezeCopy(selectedEvents),
    provenance: deepFreezeCopy(provenance),
    policy: deepFreezeCopy(session.policy),
    views: deepFreezeCopy(rebuildCurrentState(session, events)),
    audit
  };
}

function selectEvents(events: readonly EarwormEvent[], selector: ContextSelector): EarwormEvent[] {
  const direct = events.filter((event) => matchesSelector(event, selector));
  if (!selector.asset_id) {
    return direct;
  }

  const byId = new Map(events.map((event) => [event.event_id, event]));
  const selected = new Map(direct.map((event) => [event.event_id, event]));
  const visitParents = (event: EarwormEvent): void => {
    for (const parentId of event.parent_event_ids ?? []) {
      const parent = byId.get(parentId);
      if (parent && !selected.has(parent.event_id)) {
        selected.set(parent.event_id, parent);
        visitParents(parent);
      }
    }
  };

  for (const event of direct) {
    visitParents(event);
  }

  return events.filter((event) => selected.has(event.event_id));
}

function matchesSelector(event: EarwormEvent, selector: ContextSelector): boolean {
  if (selector.asset_id && !assetIdsForEvent(event).includes(selector.asset_id)) {
    return false;
  }

  if (selector.node_id && event.source.node_id !== selector.node_id) {
    return false;
  }

  if (selector.event_types && !selector.event_types.includes(event.type)) {
    return false;
  }

  if (selector.include?.length) {
    const allowed = new Set<EventType>();
    for (const include of selector.include) {
      for (const type of includeTypeGroups[include] ?? []) {
        allowed.add(type);
      }
    }
    if (!allowed.has(event.type)) {
      return false;
    }
  }

  if (selector.time_range) {
    const eventTime = eventTimeValue(event, selector.time_domain ?? "asset");
    if (typeof eventTime === "number") {
      return eventTime >= selector.time_range.start && eventTime <= selector.time_range.end;
    }
    return false;
  }

  return true;
}

function redactEvents(events: EarwormEvent[], policy: RetentionPolicy, summarization?: ContextSelector["summarization"]): EarwormEvent[] {
  const paths = new Set(policy.redaction?.sensitive_fields ?? []);
  if (summarization === "agent_safe") {
    for (const path of policy.redaction?.agent_safe_omissions ?? []) {
      paths.add(path);
    }
  }

  return events.map((event) => {
    const copy = structuredClone(event) as EarwormEvent;
    for (const path of paths) {
      deletePath(copy as JsonObject, path.split("."));
    }
    return summarization === "compact" ? compactEvent(copy) : deepFreeze(copy);
  });
}

function compactEvent(event: EarwormEvent): EarwormEvent {
  const copy = structuredClone(event) as EarwormEvent;
  if (event.type === "alignment.ingested" && Array.isArray(copy.payload.words)) {
    copy.payload = {
      asset_id: copy.payload.asset_id,
      word_count: copy.payload.words.length
    };
  }
  if (event.type === "analysis.frame" && Array.isArray(copy.payload.frames)) {
    copy.payload = {
      asset_id: copy.payload.asset_id,
      frame_count: copy.payload.frames.length,
      first_frame: copy.payload.frames[0]
    };
  }
  return deepFreeze(copy);
}

function applyContextBudget(events: EarwormEvent[], maxTokens?: number): EarwormEvent[] {
  if (!maxTokens || maxTokens <= 0) {
    return deepFreezeCopy(events);
  }
  const maxChars = maxTokens * 4;
  const selected: EarwormEvent[] = [];
  let chars = 0;
  for (const event of [...events].reverse()) {
    const eventChars = JSON.stringify(event).length;
    if (selected.length > 0 && chars + eventChars > maxChars) {
      break;
    }
    selected.push(event);
    chars += eventChars;
  }
  return deepFreezeCopy(selected.reverse());
}

function deletePath(target: JsonObject, parts: string[]): void {
  if (parts.some((part) => part === "__proto__" || part === "prototype" || part === "constructor")) {
    return;
  }
  let cursor: unknown = target;
  for (const part of parts.slice(0, -1)) {
    if (!isJsonObject(cursor)) {
      return;
    }
    const descriptor = Object.getOwnPropertyDescriptor(cursor, part);
    if (!descriptor || !("value" in descriptor)) {
      return;
    }
    cursor = descriptor.value;
  }
  if (isJsonObject(cursor)) {
    const last = parts.at(-1);
    if (last && Object.prototype.hasOwnProperty.call(cursor, last)) {
      Reflect.deleteProperty(cursor, last);
    }
  }
}

function appendIndex<K>(index: Map<K, EarwormEvent[]>, key: K, event: EarwormEvent): void {
  const events = index.get(key) ?? [];
  events.push(event);
  index.set(key, events);
}

function prepareEventForAppend(
  session: EarwormSession,
  events: readonly EarwormEvent[],
  event: EarwormEvent
): EarwormEvent {
  const previousEvent = events.at(-1);
  const prev_event_hash = previousEvent ? previousEvent.event_hash ?? hashEvent(previousEvent) : undefined;
  const candidate = deepFreezeCopy(removeUndefined({
    ...event,
    prev_event_hash
  }) as EarwormEvent);
  const appendable = deepFreezeCopy({
    ...candidate,
    event_hash: hashEvent(candidate)
  });
  assertAppendableEvent(session, events, appendable);
  return appendable;
}

function assertAppendableLoadedEvent(
  session: EarwormSession,
  events: readonly EarwormEvent[],
  event: EarwormEvent
): void {
  assertAppendableEvent(session, events, event);
  const previousEvent = events.at(-1);
  const expectedPrevHash = previousEvent ? previousEvent.event_hash ?? hashEvent(previousEvent) : undefined;
  if (event.prev_event_hash !== expectedPrevHash) {
    throw new Error(`event ${event.event_id} has invalid prev_event_hash`);
  }
  if (!event.event_hash) {
    throw new Error(`event ${event.event_id} is missing event_hash`);
  }
  const expectedEventHash = hashEvent(event);
  if (event.event_hash !== expectedEventHash) {
    throw new Error(`event ${event.event_id} has invalid event_hash`);
  }
}

function assertAppendableGeneratedAsset(store: EventStore, event: EarwormEvent, provenance?: ProvenanceRecord): void {
  assertValidEvent(event);
  const session = store.session;
  const byId = new Set(store.events.map((stored) => stored.event_id));
  if (event.session_id !== session.session_id) {
    throw new Error(`event ${event.event_id} belongs to ${event.session_id}, expected ${session.session_id}`);
  }
  if (byId.has(event.event_id)) {
    throw new Error(`duplicate event_id ${event.event_id}`);
  }
  for (const parentId of event.parent_event_ids) {
    if (!byId.has(parentId)) {
      throw new Error(`event ${event.event_id} references missing parent ${parentId}`);
    }
  }
  const provenanceIds = new Set(session.provenance.map((record) => record.provenance_id));
  if (provenance) {
    provenanceIds.add(provenance.provenance_id);
  }
  if (event.provenance_id && !provenanceIds.has(event.provenance_id)) {
    throw new Error(`event ${event.event_id} references missing provenance ${event.provenance_id}`);
  }
}

function assertAppendableEvent(session: EarwormSession, events: readonly EarwormEvent[], event: EarwormEvent): void {
  assertValidEvent(event);
  if (event.session_id !== session.session_id) {
    throw new Error(`event ${event.event_id} belongs to ${event.session_id}, expected ${session.session_id}`);
  }
  const appendedIds = new Set(events.map((appended) => appended.event_id));
  if (appendedIds.has(event.event_id)) {
    throw new Error(`duplicate event_id ${event.event_id}`);
  }
  for (const parentId of event.parent_event_ids) {
    if (!appendedIds.has(parentId)) {
      throw new Error(`event ${event.event_id} references missing parent ${parentId}`);
    }
  }
  if (
    event.provenance_id &&
    event.type !== "generation.requested" &&
    !session.provenance.some((record) => record.provenance_id === event.provenance_id)
  ) {
    throw new Error(`event ${event.event_id} references missing provenance ${event.provenance_id}`);
  }
}

function assertValidEvent(event: EarwormEvent): void {
  const errors: string[] = [];
  if (!event.event_id) {
    errors.push("event_id is required");
  }
  if (!event.session_id) {
    errors.push("session_id is required");
  }
  if (!includeAllEventTypes.has(event.type)) {
    errors.push(`unsupported event type ${event.type}`);
  }
  if (!event.time || typeof event.time.wall_clock !== "string") {
    errors.push("time.wall_clock is required");
  }
  if (!event.source || !["user", "agent", "system", "provider"].includes(event.source.actor)) {
    errors.push("source.actor is invalid");
  }
  if (!isJsonObject(event.payload)) {
    errors.push("payload must be an object");
  }
  if (!Array.isArray(event.parent_event_ids)) {
    errors.push("parent_event_ids must be an array");
  }
  if (typeof event.reversible !== "boolean") {
    errors.push("reversible must be boolean");
  }
  if (typeof event.confidence === "number" && (event.confidence < 0 || event.confidence > 1)) {
    errors.push("confidence must be between 0 and 1");
  }
  if (event.prev_event_hash !== undefined && typeof event.prev_event_hash !== "string") {
    errors.push("prev_event_hash must be a string");
  }
  if (event.event_hash !== undefined && typeof event.event_hash !== "string") {
    errors.push("event_hash must be a string");
  }
  if (errors.length > 0) {
    throw new Error(`invalid event ${event.event_id ?? "(missing)"}: ${errors.join("; ")}`);
  }
}

const includeAllEventTypes = new Set<EventType>([
  "prompt.ingested",
  "generation.requested",
  "audio.generated",
  "signal.packet.ingested",
  "alignment.ingested",
  "analysis.frame",
  "dsp.parameter.changed",
  "agent.action.proposed",
  "agent.action.applied",
  "automation.committed",
  "automation.reverted",
  "render.created",
  "snapshot.created"
]);

function selectProvenance(session: EarwormSession, selector: ContextSelector, selectedProvenanceIds: Set<string>): ProvenanceRecord[] {
  if (selector.include?.includes("provenance")) {
    if (selector.asset_id) {
      const asset = session.assets.find((candidate) => candidate.asset_id === selector.asset_id);
      return session.provenance.filter((record) => record.provenance_id === asset?.provenance_id);
    }
    return session.provenance;
  }
  return session.provenance.filter((record) => selectedProvenanceIds.has(record.provenance_id));
}

function createManifestAudit(assets: AssetRef[], events: EarwormEvent[], provenance: ProvenanceRecord[]): ManifestAudit {
  const warnings: string[] = [];
  const provenanceIds = new Set(provenance.map((record) => record.provenance_id));
  let rights_status: ManifestAudit["rights_status"] = "complete";

  for (const asset of assets) {
    if (!asset.provenance_id) {
      warnings.push(`asset ${asset.asset_id} has no provenance_id`);
      rights_status = "incomplete";
      continue;
    }
    const record = provenance.find((candidate) => candidate.provenance_id === asset.provenance_id);
    if (!record) {
      warnings.push(`asset ${asset.asset_id} references missing provenance ${asset.provenance_id}`);
      rights_status = "incomplete";
    } else if (record.consent_status === "restricted") {
      warnings.push(`asset ${asset.asset_id} has restricted consent status`);
      rights_status = "restricted";
    } else if (record.consent_status === "unknown" && rights_status !== "restricted") {
      warnings.push(`asset ${asset.asset_id} has unknown consent status`);
      rights_status = "unknown";
    }
  }

  for (const event of events) {
    if (event.provenance_id && !provenanceIds.has(event.provenance_id)) {
      warnings.push(`event ${event.event_id} references missing provenance ${event.provenance_id}`);
      if (rights_status === "complete") {
        rights_status = "incomplete";
      }
    }
  }

  return {
    asset_count: assets.length,
    event_count: events.length,
    provenance_count: provenance.length,
    rights_status,
    warnings
  };
}

function baseEvent(session_id: string, event: EventDraft): EarwormEvent {
  return removeUndefined({
    session_id,
    confidence: 1,
    ...event,
    time: {
      wall_clock: new Date().toISOString(),
      ...event.time
    }
  }) as EarwormEvent;
}

function provenanceIdForAsset(session: EarwormSession, assetId?: string): string | undefined {
  if (!assetId) {
    return undefined;
  }
  return session.assets.find((asset) => asset.asset_id === assetId)?.provenance_id;
}

function averageConfidence(items: Array<{ confidence?: number }>): number | undefined {
  const values = items.map((item) => item.confidence).filter((value): value is number => typeof value === "number");
  if (values.length === 0) {
    return undefined;
  }
  return values.reduce((sum, value) => sum + value, 0) / values.length;
}

function enforceLaneConstraints(intent: ModulationIntent, lane: AutomationLane): void {
  if (!lane.reversible) {
    throw new Error(`automation lane ${lane.lane_id} must be reversible`);
  }
  const min = intent.constraints?.min;
  const max = intent.constraints?.max;
  for (const point of lane.points ?? []) {
    if (typeof min === "number" && point.value < min) {
      throw new Error(`automation point ${point.time} is below minimum ${min}`);
    }
    if (typeof max === "number" && point.value > max) {
      throw new Error(`automation point ${point.time} is above maximum ${max}`);
    }
  }
}

function assertAutomationTraceability(
  store: EventStore,
  intent: ModulationIntent,
  lane: AutomationLane,
  parentEventIds: string[]
): void {
  if (lane.source_intent_id !== intent.intent_id) {
    throw new Error(`automation lane ${lane.lane_id} source_intent_id ${lane.source_intent_id} does not match ${intent.intent_id}`);
  }
  if (lane.target !== intent.target) {
    throw new Error(`automation lane ${lane.lane_id} target ${lane.target} does not match ${intent.target}`);
  }
  if (intent.output_lane_ref && intent.output_lane_ref !== lane.lane_id) {
    throw new Error(`intent ${intent.intent_id} output_lane_ref ${intent.output_lane_ref} does not match lane ${lane.lane_id}`);
  }

  const byId = new Map(store.events.map((event) => [event.event_id, event]));
  for (const sourceRef of intent.source_refs) {
    if (!byId.has(sourceRef)) {
      throw new Error(`intent ${intent.intent_id} references missing source ${sourceRef}`);
    }
  }

  const proposal = parentEventIds
    .map((parentId) => byId.get(parentId))
    .find((event) => event?.type === "agent.action.proposed" && isJsonObject(event.payload.intent) && event.payload.intent.intent_id === intent.intent_id);
  if (!proposal) {
    throw new Error(`automation commit for ${intent.intent_id} must parent a prior agent.action.proposed event`);
  }
}

function assetIdsForSourceRefs(events: readonly EarwormEvent[], sourceRefs: string[]): string[] {
  const byId = new Map(events.map((event) => [event.event_id, event]));
  const assetIds = new Set<string>();
  for (const sourceRef of sourceRefs) {
    const event = byId.get(sourceRef);
    if (event) {
      for (const assetId of assetIdsForEvent(event)) {
        assetIds.add(assetId);
      }
    }
  }
  return [...assetIds];
}

export function eventTimeValue(event: EarwormEvent, preference: "asset" | "project" | "wall_clock" = "asset"): number | undefined {
  if (preference === "wall_clock") {
    const millis = Date.parse(event.time.wall_clock);
    return Number.isNaN(millis) ? undefined : millis;
  }
  if (preference === "asset") {
    return event.time.asset_seconds ?? event.time.project_seconds;
  }
  return event.time.project_seconds ?? event.time.asset_seconds;
}

export function normalizeTimeReference(time: Partial<EarwormTime>, fallbackWallClock = new Date().toISOString()): EarwormTime {
  return removeUndefined({
    ...time,
    wall_clock: time.wall_clock ?? fallbackWallClock
  }) as EarwormTime;
}

export function restoreSnapshot(session: EarwormSession, events: readonly EarwormEvent[], snapshotEventId: string): EarwormSession {
  const snapshot = events.find((event) => event.event_id === snapshotEventId && event.type === "snapshot.created");
  if (!snapshot) {
    throw new Error(`snapshot ${snapshotEventId} not found`);
  }
  const eventCount = snapshot.payload.event_count;
  if (typeof eventCount !== "number") {
    throw new Error(`snapshot ${snapshotEventId} does not include numeric event_count`);
  }
  const restoredEvents = events.slice(0, eventCount);
  return {
    ...session,
    events: restoredEvents,
    views: rebuildCurrentState(session, restoredEvents)
  };
}

export function createBreathAutomationFromContext(
  bundle: ContextBundle,
  {
    intent_id = "intent_breath_generated",
    lane_id = "lane_breath_generated",
    target = "dsp.breath.mix",
    baseValue = 0.22,
    pauseBoost = 0.14,
    max = 0.62
  }: {
    intent_id?: string;
    lane_id?: string;
    target?: string;
    baseValue?: number;
    pauseBoost?: number;
    max?: number;
  } = {}
): { intent: ModulationIntent; lane: AutomationLane } {
  const promptEvent = bundle.events.find((event) => event.type === "prompt.ingested");
  const alignmentEvent = bundle.events.find((event) => event.type === "alignment.ingested");
  const prompt = typeof promptEvent?.payload.prompt === "string" ? promptEvent.payload.prompt.toLowerCase() : "";
  const breathy = prompt.includes("breath");
  const points: AutomationLane["points"] = [{ time: 0, value: baseValue, curve: "linear" }];

  const words = Array.isArray(alignmentEvent?.payload.words) ? alignmentEvent.payload.words : [];
  for (let index = 1; index < words.length; index += 1) {
    const previous = words[index - 1];
    const current = words[index];
    if (isJsonObject(previous) && isJsonObject(current) && typeof previous.end === "number" && typeof current.start === "number") {
      const gap = current.start - previous.end;
      if (gap >= 0.16) {
        points.push({ time: previous.end, value: Math.min(max, baseValue + pauseBoost), curve: "ease" as const });
        points.push({ time: current.start, value: baseValue + (breathy ? 0.05 : 0), curve: "ease" as const });
      }
    }
  }

  const intent: ModulationIntent = {
    intent_id,
    target,
    reason: "prompt_trait",
    source_refs: bundle.events
      .filter((event) => event.type === "prompt.ingested" || event.type === "alignment.ingested")
      .map((event) => event.event_id),
    mapping: {
      type: "rule",
      parameters: {
        trait: breathy ? "breathy" : "neutral",
        pause_boost: pauseBoost
      }
    },
    constraints: {
      min: 0,
      max,
      smoothing_ms: 80,
      protect_intelligibility: true
    },
    output_lane_ref: lane_id,
    confidence: breathy ? 0.78 : 0.55
  };

  return {
    intent,
    lane: {
      lane_id,
      target,
      unit: "normalized",
      points,
      source_intent_id: intent_id,
      reversible: true
    }
  };
}

function cloneSessionState(session: EarwormSession, events: readonly EarwormEvent[]): EarwormSession {
  return {
    ...session,
    policy: deepFreezeCopy(session.policy),
    assets: deepFreezeCopy(session.assets ?? []),
    events: [...events],
    provenance: deepFreezeCopy(session.provenance ?? []),
    views: deepFreezeCopy(session.views ?? { current_state: {}, summaries: [] }),
    indexes: deepFreezeCopy(session.indexes ?? {
      by_time: true,
      by_asset: true,
      by_node: true,
      by_text: true
    })
  };
}

function assertRetentionActive(policy: RetentionPolicy): void {
  if (policy.mode !== "expires_at" || !policy.expires_at) {
    return;
  }
  const expiresAt = Date.parse(policy.expires_at);
  if (!Number.isNaN(expiresAt) && expiresAt <= Date.now()) {
    throw new Error(`retention policy expired at ${policy.expires_at}`);
  }
}

function isAutomationLane(value: unknown): value is AutomationLane {
  return isJsonObject(value) &&
    typeof value.lane_id === "string" &&
    typeof value.target === "string" &&
    typeof value.unit === "string" &&
    Array.isArray(value.points) &&
    typeof value.source_intent_id === "string" &&
    typeof value.reversible === "boolean";
}

function hashEvent(event: EarwormEvent): string {
  const { event_hash: _eventHash, ...material } = event;
  return `sha256:${createHash("sha256").update(stableJson(material)).digest("hex")}`;
}

function stableJson(value: unknown): string {
  if (Array.isArray(value)) {
    return `[${value.map(stableJson).join(",")}]`;
  }
  if (isJsonObject(value)) {
    return `{${Object.keys(value)
      .sort()
      .map((key) => `${JSON.stringify(key)}:${stableJson(value[key])}`)
      .join(",")}}`;
  }
  return JSON.stringify(value);
}

function assertMatchingRegistration(kind: "asset" | "provenance record", id: string, existing: unknown, incoming: unknown): void {
  if (stableJson(removeUndefined(existing)) !== stableJson(removeUndefined(incoming))) {
    throw new Error(`${kind} ${id} is already registered with different content`);
  }
}

function textRangeKey(range: [number, number]): string {
  return `${range[0]}:${range[1]}`;
}

function overlapsTextRange(event: EarwormEvent, start: number, end: number): boolean {
  const ranges = [event.time.char_range, event.time.word_range].filter((range): range is [number, number] => Boolean(range));
  return ranges.some(([rangeStart, rangeEnd]) => rangeStart <= end && rangeEnd >= start);
}

function uniqueEvents(events: EarwormEvent[]): EarwormEvent[] {
  const seen = new Set<string>();
  return events.filter((event) => {
    if (seen.has(event.event_id)) {
      return false;
    }
    seen.add(event.event_id);
    return true;
  });
}

function assetIdsForEvent(event: EarwormEvent): string[] {
  const ids = new Set<string>();
  if (typeof event.payload.asset_id === "string") {
    ids.add(event.payload.asset_id);
  }
  if (Array.isArray(event.payload.asset_ids)) {
    for (const assetId of event.payload.asset_ids) {
      if (typeof assetId === "string") {
        ids.add(assetId);
      }
    }
  }
  const frames = event.payload.frames;
  if (Array.isArray(frames)) {
    for (const frame of frames) {
      if (isJsonObject(frame) && typeof frame.asset_ref === "string") {
        ids.add(frame.asset_ref);
      }
    }
  }
  const packet = event.payload.packet;
  if (isJsonObject(packet) && typeof packet.asset_ref === "string") {
    ids.add(packet.asset_ref);
  }
  return [...ids];
}

function deepFreezeCopy<T>(value: T): T {
  return deepFreeze(structuredClone(value));
}

function deepFreeze<T>(value: T): T {
  if (isJsonObject(value) || Array.isArray(value)) {
    for (const child of Object.values(value)) {
      deepFreeze(child);
    }
    return Object.freeze(value);
  }
  return value;
}

function isJsonObject(value: unknown): value is JsonObject {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function removeUndefined(value: unknown): unknown {
  if (Array.isArray(value)) {
    return value.map(removeUndefined);
  }
  if (!isJsonObject(value)) {
    return value;
  }
  return Object.fromEntries(
    Object.entries(value)
      .filter(([, child]) => child !== undefined)
      .map(([key, child]) => [key, removeUndefined(child)])
  );
}
