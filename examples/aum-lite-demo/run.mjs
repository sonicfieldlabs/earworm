/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

import { readFile } from "node:fs/promises";
import { createBreathAutomationFromContext, queryContext } from "../../packages/core/dist/index.js";

const session = JSON.parse(await readFile(new URL("../../packages/core/fixtures/aum-voice-generation.session.json", import.meta.url), "utf8"));
const bundle = queryContext(session, session.events, {
  asset_id: "asset_voice_line_001",
  include: ["prompt", "alignment", "analysis", "provenance"]
});
const { intent, lane } = createBreathAutomationFromContext(bundle, {
  intent_id: "intent_example_breath_001",
  lane_id: "lane_example_breath_001"
});

console.log(JSON.stringify({
  example: "aum-lite-demo",
  context_events: bundle.events.length,
  provenance_records: bundle.provenance.length,
  intent: intent.intent_id,
  lane_points: lane.points.length
}));
