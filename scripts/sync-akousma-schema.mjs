#!/usr/bin/env node

import { copyFile } from "node:fs/promises";
import { join } from "node:path";

const root = new URL("..", import.meta.url).pathname;
for (const filename of ["akousma-1.8.schema.json", "spectral-bundle.schema.json", "embedding-space.schema.json", "analysis-evidence.schema.json", "model-deployment.schema.json", "bundle-manifest.schema.json", "akousma.schema.json", "akousma-1.7.schema.json", "listening-access.schema.json", "listening-context.schema.json", "matter-context.schema.json", "transformation-graph.schema.json", "auditum-view.schema.json", "transposition-recipe.schema.json"]) {
  await copyFile(
    join(root, "packages/core/schemas", filename),
    join(root, "packages/py-akousma/akousma", filename)
  );
}
console.log("synced canonical listening schemas into py-akousma");
