/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

import { strict as assert } from "node:assert";
import {
  EarwormClient,
  InMemoryEventStore,
  createSession,
  createAkousma,
  akousmaRelation,
  addListening,
  akousmaShapeErrors,
  germImportUrl,
  newAkousmaId
} from "../packages/sdk-js/src/index.js";

const policy = {
  mode: "project_lifetime",
  local_only: true,
  redaction: {
    sensitive_fields: [],
    agent_safe_omissions: []
  }
};

const client = EarwormClient.create({
  session_id: "sess_sdk_001",
  app_id: "sdk-test",
  policy,
  created_at: "2026-05-25T19:00:00.000Z"
});

client.ingestPrompt({
  event_id: "evt_sdk_prompt_001",
  prompt: "close and breathy",
  time: { wall_clock: "2026-05-25T19:00:01.000Z" }
});

const bundle = client.queryContext({ include: ["prompt"] });

assert.equal(client.session_id, "sess_sdk_001");
assert.equal(client.events.length, 1);
assert.equal(bundle.events.length, 1);
assert.equal(client.exportManifest({ manifest_id: "manifest_sdk_001" }).manifest_id, "manifest_sdk_001");

const storeBackedSession = createSession({
  session_id: "sess_sdk_store_001",
  app_id: "sdk-store-test",
  policy,
  created_at: "2026-05-25T19:10:00.000Z"
});
const storeBacked = new InMemoryEventStore(storeBackedSession);
const storeBackedClient = new EarwormClient({ store: storeBacked });
storeBackedClient.append({
  event_id: "evt_sdk_store_prompt_001",
  session_id: "sess_sdk_store_001",
  type: "prompt.ingested",
  time: { wall_clock: "2026-05-25T19:10:01.000Z" },
  source: { actor: "user" },
  payload: { prompt: "store-backed client" },
  reversible: false,
  parent_event_ids: []
});
assert.equal(storeBackedClient.session_id, "sess_sdk_store_001");
assert.equal(storeBackedClient.events.length, 1);

// ── akousma helpers ──

const parent = createAkousma({
  audio: { asset_id: "cap_1", uri: "akousmata://objects/x.wav", duration_seconds: 8 },
  originatingApp: "oida",
  sourceType: "recorded",
  origin: "live-input",
  listening: { "akouo.describe": { summary: "warm synthesizer drone" } },
  tags: ["drone"]
});
assert.equal(akousmaShapeErrors(parent).length, 0);
assert.ok(parent.akousma_id.startsWith("akm_"));
assert.equal(parent.provenance.originating_app, "oida");

const child = createAkousma({
  audio: { asset_id: "gen_1" },
  originatingApp: "germ",
  sourceType: "generated",
  origin: "generated",
  parentAkousmaIds: [parent.akousma_id],
  operation: "transform",
  prompt: "make it metallic",
  model: "stable-audio-3"
});
assert.deepEqual(child.lineage.parent_akousma_ids, [parent.akousma_id]);
assert.equal(child.lineage.prompt, "make it metallic");

assert.ok(akousmaShapeErrors({ akousma_id: "x" }).length > 0);
assert.ok(
  akousmaShapeErrors({ ...parent, provenance: { ...parent.provenance, source_type: "bogus" } }).length > 0
);

// v1.1: summary, typed relations, listening envelope
const sibling = createAkousma({
  audio: { asset_id: "cap_2" },
  originatingApp: "oida",
  summary: "same drone, one year later",
  relations: [akousmaRelation("series_with", parent.akousma_id, "same position, later take")]
});
assert.equal(akousmaShapeErrors(sibling).length, 0);
assert.equal(sibling.summary, "same drone, one year later");
assert.deepEqual(sibling.lineage.relations, [
  { type: "series_with", target_akousma_id: parent.akousma_id, note: "same position, later take" }
]);
assert.deepEqual(sibling.lineage.parent_akousma_ids, []);

assert.throws(() => akousmaRelation("cousin_of", parent.akousma_id));
assert.ok(
  akousmaShapeErrors({
    ...sibling,
    lineage: { ...sibling.lineage, relations: [{ type: "series_with" }] }
  }).length > 0
);

addListening(sibling, "akouo.memory-lineage-listening", { main_reading: "recurrence" }, {
  contract: "akouo/v0.6",
  summary: "second in series"
});
assert.equal(sibling.listening["akouo.memory-lineage-listening"].contract, "akouo/v0.6");
assert.deepEqual(sibling.listening["akouo.memory-lineage-listening"].payload, { main_reading: "recurrence" });
assert.equal(akousmaShapeErrors(sibling).length, 0);

assert.equal(
  germImportUrl("http://127.0.0.1:5178/", parent.akousma_id, "lineage"),
  `http://127.0.0.1:5178/import?akousma=${parent.akousma_id}&mode=lineage`
);
assert.throws(() => germImportUrl("http://x", "akm_1", "bogus"));

// v1.2: location, capture, open records
const walk = createAkousma({
  audio: { asset_id: "walk_1" },
  originatingApp: "oida",
  origin: "live-input",
  location: { lat: 6.2442, lon: -75.5812, label: "río Medellín", source: "gps" },
  capture: { direction: "past", seconds: 30, trigger: "remote-ear" }
});
assert.equal(akousmaShapeErrors(walk).length, 0);
assert.equal(walk.location.lat, 6.2442);
assert.equal(walk.capture.direction, "past");
assert.ok(akousmaShapeErrors({ ...walk, location: { lat: 123, lon: 0 } }).length > 0);
assert.ok(akousmaShapeErrors({ ...walk, capture: { direction: "sideways" } }).length > 0);
assert.throws(() =>
  createAkousma({ audio: { asset_id: "x" }, originatingApp: "oida", location: { lat: 91, lon: 0 } })
);
assert.throws(() =>
  createAkousma({ audio: { asset_id: "x" }, originatingApp: "oida", capture: { direction: "sideways" } })
);
assert.equal(akousmaShapeErrors({ ...walk, weather: "light rain" }).length, 0);

const ids = new Set(Array.from({ length: 50 }, () => newAkousmaId()));
assert.equal(ids.size, 50);

console.log("test: sdk-js client passed (incl. akousma helpers)");
