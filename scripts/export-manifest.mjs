/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

import { readFile, writeFile } from "node:fs/promises";
import { dirname, resolve } from "node:path";
import { mkdir } from "node:fs/promises";
import { exportManifest } from "../packages/core/dist/index.js";

function parseArgs(argv) {
  const args = {};
  for (let index = 0; index < argv.length; index += 2) {
    const key = argv[index];
    const value = argv[index + 1];
    if (!key?.startsWith("--") || !value) {
      throw new Error("usage: node scripts/export-manifest.mjs --session path --asset asset_id --out path");
    }
    args[key.slice(2)] = value;
  }
  return args;
}

const args = parseArgs(process.argv.slice(2));
if (!args.session || !args.asset || !args.out) {
  throw new Error("usage: node scripts/export-manifest.mjs --session path --asset asset_id --out path");
}

const sessionPath = resolve(args.session);
const outPath = resolve(args.out);
const session = JSON.parse(await readFile(sessionPath, "utf8"));

const manifest = exportManifest(session, session.events, {
  manifest_id: `manifest_${args.asset}`,
  asset_id: args.asset,
  require_complete_provenance: true,
  created_at: session.created_at
});

await mkdir(dirname(outPath), { recursive: true });
await writeFile(outPath, `${JSON.stringify(manifest, null, 2)}\n`);

console.log(`manifest: wrote ${outPath}`);
