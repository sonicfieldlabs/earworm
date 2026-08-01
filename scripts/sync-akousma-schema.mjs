#!/usr/bin/env node

import { copyFile } from "node:fs/promises";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname;
await copyFile(
  join(root, "packages/core/schemas/akousma.schema.json"),
  join(root, "packages/py-akousma/akousma/akousma.schema.json")
);

console.log("synced canonical akousma schema into py-akousma");
