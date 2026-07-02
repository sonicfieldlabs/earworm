/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

import { readdir, readFile } from "node:fs/promises";
import { join } from "node:path";
import { InMemoryEventStore, createSession } from "../packages/core/dist/index.js";

const root = new URL("..", import.meta.url).pathname;
const coreFixtures = await readdir(join(root, "packages/core/fixtures"));
const testFixtures = await readdir(join(root, "tests/fixtures"));

const required = [
  ["AUM session fixture", coreFixtures.includes("aum-voice-generation.session.json")],
  ["batch render session fixture", coreFixtures.includes("batch-render.session.json")],
  ["PhonoStack sidecar session fixture", coreFixtures.includes("phonostack-sidecar.session.json")],
  ["signal packet fixture", testFixtures.includes("aum-voice-generation.signal-packet.json")],
  ["feature stream ref fixture", testFixtures.includes("aum-voice-generation.feature-stream-ref.json")],
  ["export manifest fixture", testFixtures.includes("aum-voice-generation.export-manifest.json")],
  ["germ mapping session fixture", testFixtures.includes("germ-organism-mapping.session.json")]
];

const missing = required.filter(([, ok]) => !ok).map(([label]) => label);
if (missing.length > 0) {
  console.error(`conformance: missing ${missing.join(", ")}`);
  process.exit(1);
}

const vectorDir = join(root, "tests/conformance/vectors");
const vectors = (await readdir(vectorDir))
  .filter((file) => file.endsWith(".vector.json"))
  .sort();

let checked = 0;
for (const file of vectors) {
  const vector = JSON.parse(await readFile(join(vectorDir, file), "utf8"));
  const session = createSession(vector.session);
  const store = new InMemoryEventStore(session);
  let error;
  try {
    for (const event of vector.events) {
      store.append(event);
    }
  } catch (caught) {
    error = caught;
  }

  if (vector.expect === "accept" && error) {
    throw new Error(`${file}: expected accept, got ${error.message}`);
  }
  if (vector.expect === "reject") {
    if (!error) {
      throw new Error(`${file}: expected reject`);
    }
    if (vector.error_contains && !error.message.includes(vector.error_contains)) {
      throw new Error(`${file}: expected error containing ${vector.error_contains}, got ${error.message}`);
    }
  }
  checked += 1;
}

console.log(`conformance: required fixture set is present; ${checked} vectors checked`);
