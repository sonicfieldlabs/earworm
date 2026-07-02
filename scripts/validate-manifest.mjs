/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

import { readFile } from "node:fs/promises";

const manifestPath = process.argv[2];
if (!manifestPath) {
  throw new Error("usage: node scripts/validate-manifest.mjs path/to/manifest.json");
}

const manifest = JSON.parse(await readFile(manifestPath, "utf8"));
const errors = [];

for (const key of ["manifest_id", "session_id", "app_id", "created_at", "scope", "assets", "events", "provenance", "policy", "views", "audit"]) {
  if (!(key in manifest)) {
    errors.push(`missing required field ${key}`);
  }
}

const provenanceIds = new Set((manifest.provenance ?? []).map((record) => record.provenance_id));
for (const asset of manifest.assets ?? []) {
  if (!asset.provenance_id) {
    errors.push(`asset ${asset.asset_id} has no provenance_id`);
  } else if (!provenanceIds.has(asset.provenance_id)) {
    errors.push(`asset ${asset.asset_id} references missing provenance ${asset.provenance_id}`);
  }
}

for (const event of manifest.events ?? []) {
  if (!event.event_id || !event.type || !event.time?.wall_clock || !event.source?.actor) {
    errors.push(`event ${event.event_id ?? "(missing)"} is incomplete`);
  }
}

if (manifest.audit?.warnings?.length) {
  errors.push(...manifest.audit.warnings.map((warning) => `audit warning: ${warning}`));
}

if (errors.length > 0) {
  console.error(errors.join("\n"));
  process.exit(1);
}

console.log(`manifest: ${manifestPath} is valid`);
