/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

import { readFile } from "node:fs/promises";
import { exportManifest } from "../../packages/core/dist/index.js";

const session = JSON.parse(await readFile(new URL("../../packages/core/fixtures/batch-render.session.json", import.meta.url), "utf8"));
const manifest = exportManifest(session, session.events, {
  manifest_id: "manifest_batch_render_example",
  asset_id: "asset_batch_voice_001",
  require_complete_provenance: true
});

console.log(JSON.stringify({
  example: "batch-render-manifest",
  manifest_id: manifest.manifest_id,
  event_count: manifest.audit.event_count,
  warnings: manifest.audit.warnings.length
}));
