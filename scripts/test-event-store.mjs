/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

import { strict as assert } from "node:assert";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
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
  createBreathAutomationFromContext,
  rebuildCurrentState,
  revertAutomation,
  restoreSnapshot,
  queryContext
} from "../packages/core/dist/index.js";

const root = new URL("..", import.meta.url).pathname;
const fixture = JSON.parse(
  await readFile(join(root, "packages/core/fixtures/aum-voice-generation.session.json"), "utf8")
);

const session = createSession({
  session_id: fixture.session_id,
  app_id: fixture.app_id,
  created_at: fixture.created_at,
  policy: fixture.policy,
  assets: fixture.assets,
  provenance: fixture.provenance
});

const store = new InMemoryEventStore(session);
for (const event of fixture.events) {
  store.append(event);
}

assert.equal(store.events.length, fixture.events.length);
assert.equal(store.byType("prompt.ingested").length, 1);
assert.equal(store.byAsset("asset_voice_line_001").length, 5);
assert.equal(store.byNode("earworm.mapper.breath").length, 2);
assert.throws(() => {
  store.events.pop();
});
assert.equal(store.events.length, fixture.events.length);

const rebuilt = rebuildCurrentState(store.session, store.events);
assert.equal(rebuilt.current_state.active_asset_id, "asset_voice_line_001");
assert.equal(rebuilt.current_state.latest_render_id, "render_voice_line_001");
assert.equal(rebuilt.current_state.event_count, fixture.events.length);

const bundle = queryContext(store.session, store.events, {
  asset_id: "asset_voice_line_001",
  include: ["prompt", "generation", "alignment", "analysis", "automation", "renders"],
  summarization: "compact",
  max_tokens: 3000
});

assert.equal(bundle.session_id, fixture.session_id);
assert.equal(bundle.events.length, 8);
assert.equal(bundle.assets.length, 1);
assert.equal(bundle.provenance.length, 1);
assert.equal(Object.isFrozen(bundle.assets[0]), true);
assert.throws(() => {
  bundle.assets[0].uri = "rewritten.wav";
});

const redactedDefault = queryContext(store.session, store.events, { include: ["generation"] });
const redactedGeneration = redactedDefault.events.find((event) => event.type === "generation.requested");
assert.equal(redactedGeneration.payload.provider_request.api_key, undefined);

const manifest = exportManifest(store.session, store.events, {
  manifest_id: "manifest_voice_line_001",
  asset_id: "asset_voice_line_001",
  require_complete_provenance: true
});

assert.equal(manifest.session_id, fixture.session_id);
assert.equal(manifest.assets.length, 1);
assert.equal(manifest.provenance.length, 1);
assert.equal(manifest.events.length, 8);

const generatedSession = createSession({
  session_id: "sess_generated_api_001",
  app_id: "api-test",
  created_at: "2026-05-25T18:00:00.000Z",
  policy: fixture.policy
});
const generatedStore = new InMemoryEventStore(generatedSession);
ingestPrompt(generatedStore, {
  event_id: "evt_api_prompt_001",
  prompt: "tired detective, close and breathy",
  metadata: { traits: ["tired", "breathy"] },
  time: { wall_clock: "2026-05-25T18:00:01.000Z", project_seconds: 0 }
});
ingestGenerationRequest(generatedStore, {
  event_id: "evt_api_generation_request_001",
  provider: "example-tts",
  request: { text: "The room had started listening back.", request_hash: "sha256:api-request" },
  provenance_id: "prov_api_voice_001",
  parent_event_ids: ["evt_api_prompt_001"],
  time: { wall_clock: "2026-05-25T18:00:02.000Z", project_seconds: 0 }
});
ingestGeneratedAsset(generatedStore, {
  event_id: "evt_api_audio_001",
  asset: {
    asset_id: "asset_api_voice_001",
    type: "audio",
    duration_seconds: 2.1,
    provenance_id: "prov_api_voice_001"
  },
  provenance: {
    provenance_id: "prov_api_voice_001",
    source_type: "generated",
    provider: "example-tts",
    model_id: "voice-model-preview",
    voice_id: "voice_detective_001",
    request_hash: "sha256:api-request",
    asset_hash: "sha256:api-asset",
    consent_status: "owned",
    usage_constraints: ["test"],
    created_at: "2026-05-25T18:00:03.000Z"
  },
  parent_event_ids: ["evt_api_generation_request_001"],
  time: { wall_clock: "2026-05-25T18:00:03.000Z", asset_seconds: 0 }
});
ingestAlignment(generatedStore, {
  event_id: "evt_alignment_1",
  asset_id: "asset_api_voice_001",
  alignment: {
    words: [{ text: "The", start: 0.1, end: 0.24 }],
    confidence: 0.9
  },
  parent_event_ids: ["evt_api_audio_001"],
  time: { wall_clock: "2026-05-25T18:00:04.000Z", asset_seconds: 0.1 }
});
ingestAnalysis(generatedStore, {
  event_id: "evt_api_analysis_001",
  asset_id: "asset_api_voice_001",
  frames: [
    {
      frame_id: "frame_api_001",
      asset_ref: "asset_api_voice_001",
      time_range: { start: 0, end: 0.5, unit: "seconds" },
      features: { pitch_hz: 110 },
      confidence: 0.8
    }
  ],
  parent_event_ids: ["evt_api_audio_001"],
  time: { wall_clock: "2026-05-25T18:00:05.000Z", asset_seconds: 0 }
});
ingestSignalPacket(generatedStore, {
  event_id: "evt_api_packet_001",
  packet: {
    packet_id: "packet_api_voice_001",
    signal_type: "audio",
    asset_ref: "asset_api_voice_001",
    segment_id: "segment_api_line_001",
    time_range: { start: 0, end: 2.1, unit: "seconds" },
    context_refs: ["evt_api_prompt_001", "evt_api_audio_001"],
    features_ref: "evt_api_analysis_001",
    provenance_id: "prov_api_voice_001",
    tags: ["voice", "generated"]
  },
  parent_event_ids: ["evt_api_audio_001", "evt_api_analysis_001"],
  time: { wall_clock: "2026-05-25T18:00:05.500Z", asset_seconds: 0 }
});
const intent = {
  intent_id: "intent_api_breath_001",
  target: "dsp.breath.mix",
  reason: "prompt_trait",
  source_refs: ["evt_api_prompt_001", "evt_alignment_1"],
  mapping: { type: "rule", parameters: { trait: "breathy" } },
  constraints: { min: 0, max: 0.6, smoothing_ms: 80, protect_intelligibility: true },
  output_lane_ref: "lane_api_breath_001",
  confidence: 0.77
};
emitModulationIntent(generatedStore, {
  event_id: "evt_api_intent_001",
  intent,
  parent_event_ids: ["evt_api_prompt_001", "evt_alignment_1"],
  time: { wall_clock: "2026-05-25T18:00:06.000Z", asset_seconds: 0 }
});
commitAutomation(generatedStore, {
  event_id: "evt_api_automation_001",
  intent,
  lane: {
    lane_id: "lane_api_breath_001",
    target: "dsp.breath.mix",
    unit: "normalized",
    points: [
      { time: 0, value: 0.25 },
      { time: 1.2, value: 0.38 }
    ],
    source_intent_id: "intent_api_breath_001",
    reversible: true
  },
  parent_event_ids: ["evt_api_intent_001"],
  time: { wall_clock: "2026-05-25T18:00:07.000Z", asset_seconds: 0 }
});
revertAutomation(generatedStore, "evt_api_automation_001", {
  event_id: "evt_api_revert_001",
  time: { wall_clock: "2026-05-25T18:00:07.500Z", asset_seconds: 0 }
});
createSnapshot(generatedStore, {
  event_id: "evt_api_snapshot_001",
  label: "after breath automation",
  time: { wall_clock: "2026-05-25T18:00:08.000Z", project_seconds: 0 }
});

assert.equal(generatedStore.events.length, 10);
assert.equal(generatedStore.session.assets.length, 1);
assert.equal(generatedStore.session.provenance.length, 1);
assert.equal(generatedStore.byTimeRange(0, 0.2).length >= 4, true);
assert.equal(generatedStore.events.every((event) => event.event_hash?.startsWith("sha256:")), true);
const revertEvent = generatedStore.events.find((event) => event.event_id === "evt_api_revert_001");
assert.equal(revertEvent.payload.lane.rollback_lane_ref, "lane_api_breath_001");
assert.throws(() => {
  ingestPrompt(generatedStore, {
    event_id: "evt_api_prompt_001",
    prompt: "duplicate id",
    time: { wall_clock: "2026-05-25T18:00:09.000Z" }
  });
}, /duplicate event_id/);
assert.throws(() => {
  generatedStore.append({
    ...generatedStore.events[0],
    event_id: "evt_missing_parent_001",
    parent_event_ids: ["evt_nope"]
  });
}, /missing parent/);

const tmpRoot = await mkdtemp(join(tmpdir(), "earworm-jsonl-"));
const jsonlPath = join(tmpRoot, "events.jsonl");
const jsonlStore = await JsonlEventStore.create(jsonlPath, session);
for (const event of fixture.events) {
  await jsonlStore.appendAndPersist(event);
}

const loadedJsonlStore = await JsonlEventStore.load(jsonlPath, session);
assert.equal(loadedJsonlStore.events.length, fixture.events.length);
assert.equal(loadedJsonlStore.byAsset("asset_voice_line_001").length, 5);
assert.equal(loadedJsonlStore.session.views.current_state.latest_render_id, "render_voice_line_001");
assert.equal(loadedJsonlStore.events.every((event) => event.event_hash?.startsWith("sha256:")), true);

const wrongSession = createSession({
  session_id: "sess_wrong_jsonl_001",
  app_id: fixture.app_id,
  created_at: fixture.created_at,
  policy: fixture.policy,
  assets: fixture.assets,
  provenance: fixture.provenance
});
await assert.rejects(JsonlEventStore.load(jsonlPath, wrongSession), /expected sess_wrong_jsonl_001/);

const tamperedJsonlPath = join(tmpRoot, "events-tampered.jsonl");
const tamperedText = (await readFile(jsonlPath, "utf8")).replace("tired detective", "rewritten detective");
await writeFile(tamperedJsonlPath, tamperedText);
await assert.rejects(JsonlEventStore.load(tamperedJsonlPath, session), /invalid event_hash/);

const gapJsonlPath = join(tmpRoot, "events-gap.jsonl");
const gapStore = await JsonlEventStore.create(gapJsonlPath, generatedSession);
gapStore.append({
  event_id: "evt_gap_parent_001",
  session_id: generatedSession.session_id,
  type: "prompt.ingested",
  time: { wall_clock: "2026-05-25T18:20:00.000Z" },
  source: { actor: "user" },
  payload: { prompt: "parent in memory before persist" },
  reversible: false,
  parent_event_ids: []
});
await gapStore.appendAndPersist({
  event_id: "evt_gap_child_001",
  session_id: generatedSession.session_id,
  type: "generation.requested",
  time: { wall_clock: "2026-05-25T18:20:01.000Z" },
  source: { actor: "system" },
  payload: { provider: "example-tts" },
  reversible: false,
  parent_event_ids: ["evt_gap_parent_001"]
});
const loadedGapStore = await JsonlEventStore.load(gapJsonlPath, generatedSession);
assert.equal(loadedGapStore.events.length, 2);

const provenanceOnly = queryContext(store.session, store.events, { include: ["provenance"] });
assert.equal(provenanceOnly.provenance.length, 1);
assert.equal(provenanceOnly.events.length, 0);

const breathBundle = queryContext(store.session, store.events, {
  asset_id: "asset_voice_line_001",
  include: ["prompt", "alignment"]
});
const mapped = createBreathAutomationFromContext(breathBundle, {
  intent_id: "intent_test_breath",
  lane_id: "lane_test_breath"
});
assert.equal(mapped.intent.output_lane_ref, "lane_test_breath");
assert.equal(mapped.lane.points.every((point) => point.value <= mapped.intent.constraints.max), true);

createSnapshot(store, {
  event_id: "evt_snapshot_for_restore",
  label: "restore point",
  time: { wall_clock: "2026-05-25T18:10:00.000Z", project_seconds: 0 }
});
const restored = restoreSnapshot(store.session, store.events, "evt_snapshot_for_restore");
assert.equal(restored.events.length, fixture.events.length);

console.log("test: event store reconstruction and selectors passed");
