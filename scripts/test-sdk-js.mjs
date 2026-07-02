/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

import { strict as assert } from "node:assert";
import { EarwormClient, InMemoryEventStore, createSession } from "../packages/sdk-js/src/index.js";

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

console.log("test: sdk-js client passed");
