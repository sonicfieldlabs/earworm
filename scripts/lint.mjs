/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

import { readFile, readdir } from "node:fs/promises";
import { extname, join } from "node:path";

const root = new URL("..", import.meta.url).pathname;
const ignoredDirs = new Set([
  ".git",
  ".mypy_cache",
  ".pytest_cache",
  ".ruff_cache",
  ".venv",
  "__pycache__",
  "dist",
  "node_modules"
]);
const textExtensions = new Set([".md", ".json", ".yaml", ".yml", ".js", ".mjs", ".ts", ".py", ".toml"]);

async function walk(dir) {
  const entries = await readdir(dir, { withFileTypes: true });
  const files = [];
  for (const entry of entries) {
    if (ignoredDirs.has(entry.name)) {
      continue;
    }
    const path = join(dir, entry.name);
    if (entry.isDirectory()) {
      files.push(...(await walk(path)));
    } else {
      files.push(path);
    }
  }
  return files;
}

const files = (await walk(root)).filter((file) => textExtensions.has(extname(file)));
const errors = [];

for (const file of files) {
  const text = await readFile(file, "utf8");
  const relative = file.slice(root.length + 1);

  if (text.includes("\t")) {
    errors.push(`${relative}: contains tab characters`);
  }
  if (!text.endsWith("\n")) {
    errors.push(`${relative}: missing trailing newline`);
  }

  const lines = text.split("\n");
  lines.forEach((line, index) => {
    if (/[ \t]$/.test(line)) {
      errors.push(`${relative}:${index + 1}: trailing whitespace`);
    }
  });

  if (extname(file) === ".json") {
    try {
      JSON.parse(text);
    } catch (error) {
      errors.push(`${relative}: invalid JSON: ${error.message}`);
    }
  }
}

if (errors.length > 0) {
  console.error(errors.join("\n"));
  process.exit(1);
}

console.log(`lint: checked ${files.length} text files`);
