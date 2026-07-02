/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

import { readFile } from "node:fs/promises";
import { queryContext } from "../../packages/core/dist/index.js";

const session = JSON.parse(await readFile(new URL("../../packages/core/fixtures/phonostack-sidecar.session.json", import.meta.url), "utf8"));
const bundle = queryContext(session, session.events, {
  asset_id: "asset_studio_clip_001",
  include: ["prompt", "signal", "generation", "provenance"],
  summarization: "agent_safe"
});

console.log(JSON.stringify({
  example: "phonostack-studio-sidecar",
  context_events: bundle.events.length,
  assets: bundle.assets.length,
  provenance_records: bundle.provenance.length
}));
