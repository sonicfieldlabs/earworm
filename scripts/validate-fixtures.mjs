/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

import { readdir, readFile } from "node:fs/promises";
import { basename, join } from "node:path";

const root = new URL("..", import.meta.url).pathname;
const schemaDir = join(root, "packages/core/schemas");

async function readJson(path) {
  return JSON.parse(await readFile(path, "utf8"));
}

async function loadSchemas() {
  const files = (await readdir(schemaDir)).filter((file) => file.endsWith(".schema.json"));
  const schemas = new Map();

  for (const file of files) {
    const schema = await readJson(join(schemaDir, file));
    assertSupportedSchema(schema, file);
    schemas.set(file, schema);
    schemas.set(schema.$id, schema);
  }

  return schemas;
}

function assertSupportedSchema(schema, label, path = "$") {
  const supported = new Set([
    "$schema",
    "$id",
    "$ref",
    "title",
    "type",
    "required",
    "additionalProperties",
    "properties",
    "items",
    "enum",
    "minItems",
    "maxItems",
    "minimum",
    "maximum"
  ]);

  for (const key of Object.keys(schema)) {
    if (!supported.has(key)) {
      throw new Error(`${label} ${path}: unsupported schema keyword ${key}`);
    }
  }

  for (const [key, childSchema] of Object.entries(schema.properties ?? {})) {
    assertSupportedSchema(childSchema, label, `${path}.properties.${key}`);
  }
  if (schema.items) {
    assertSupportedSchema(schema.items, label, `${path}.items`);
  }
}

function validate(schema, value, schemas, path = "$") {
  const errors = [];

  if (schema.$ref) {
    const ref = schemas.get(schema.$ref) ?? schemas.get(basename(schema.$ref));
    if (!ref) {
      return [`${path}: unresolved schema ref ${schema.$ref}`];
    }
    errors.push(...validate(ref, value, schemas, path));
  }

  if (schema.type) {
    const actual = Array.isArray(value) ? "array" : value === null ? "null" : typeof value;
    if (schema.type === "integer") {
      if (!Number.isInteger(value)) {
        errors.push(`${path}: expected integer, got ${actual}`);
        return errors;
      }
    } else if (schema.type === "number") {
      if (typeof value !== "number" || Number.isNaN(value)) {
        errors.push(`${path}: expected number, got ${actual}`);
        return errors;
      }
    } else if (schema.type !== actual) {
      errors.push(`${path}: expected ${schema.type}, got ${actual}`);
      return errors;
    }
  }

  if (schema.enum && !schema.enum.includes(value)) {
    errors.push(`${path}: expected one of ${schema.enum.join(", ")}, got ${JSON.stringify(value)}`);
  }

  if (typeof value === "number") {
    if (typeof schema.minimum === "number" && value < schema.minimum) {
      errors.push(`${path}: expected >= ${schema.minimum}, got ${value}`);
    }
    if (typeof schema.maximum === "number" && value > schema.maximum) {
      errors.push(`${path}: expected <= ${schema.maximum}, got ${value}`);
    }
  }

  if (schema.type === "object") {
    const required = schema.required ?? [];
    for (const key of required) {
      if (!(key in value)) {
        errors.push(`${path}.${key}: required property missing`);
      }
    }

    if (schema.additionalProperties === false) {
      const allowed = new Set(Object.keys(schema.properties ?? {}));
      for (const key of Object.keys(value)) {
        if (!allowed.has(key)) {
          errors.push(`${path}.${key}: additional property not allowed`);
        }
      }
    }

    for (const [key, childSchema] of Object.entries(schema.properties ?? {})) {
      if (key in value) {
        errors.push(...validate(childSchema, value[key], schemas, `${path}.${key}`));
      }
    }
  }

  if (schema.type === "array") {
    if (schema.minItems !== undefined && value.length < schema.minItems) {
      errors.push(`${path}: expected at least ${schema.minItems} items`);
    }
    if (schema.maxItems !== undefined && value.length > schema.maxItems) {
      errors.push(`${path}: expected at most ${schema.maxItems} items`);
    }
    if (schema.items) {
      value.forEach((item, index) => {
        errors.push(...validate(schema.items, item, schemas, `${path}[${index}]`));
      });
    }
  }

  return errors;
}

function assertValid(label, schema, value, schemas) {
  const errors = validate(schema, value, schemas);
  if (errors.length > 0) {
    throw new Error(`${label} failed validation:\n${errors.join("\n")}`);
  }
}

function assertKnownPayloads(label, event, schemas) {
  if (event.payload?.intent) {
    assertValid(`${label} modulation intent`, schemas.get("modulation-intent.schema.json"), event.payload.intent, schemas);
  }
  if (event.payload?.lane) {
    assertValid(`${label} automation lane`, schemas.get("automation-lane.schema.json"), event.payload.lane, schemas);
  }
  for (const frame of event.payload?.frames ?? []) {
    assertValid(`${label} analysis frame ${frame.frame_id}`, schemas.get("analysis-frame.schema.json"), frame, schemas);
  }
  if (event.payload?.packet) {
    assertValid(`${label} signal packet`, schemas.get("signal-packet.schema.json"), event.payload.packet, schemas);
  }
}

function assertSessionIntegrity(label, session) {
  const eventIds = new Set(session.events.map((event) => event.event_id));
  const provenanceIds = new Set(session.provenance.map((record) => record.provenance_id));

  for (const event of session.events) {
    for (const parentId of event.parent_event_ids ?? []) {
      if (!eventIds.has(parentId)) {
        throw new Error(`${label}: ${event.event_id} references missing parent ${parentId}`);
      }
    }
    if (event.provenance_id && !provenanceIds.has(event.provenance_id)) {
      throw new Error(`${label}: ${event.event_id} references missing provenance ${event.provenance_id}`);
    }
  }

  for (const asset of session.assets) {
    if (asset.provenance_id && !provenanceIds.has(asset.provenance_id)) {
      throw new Error(`${label}: ${asset.asset_id} references missing provenance ${asset.provenance_id}`);
    }
  }
}

const schemas = await loadSchemas();
const schemaBySuffix = {
  ".session.json": "earworm-session.schema.json",
  ".signal-packet.json": "signal-packet.schema.json",
  ".feature-stream-ref.json": "feature-stream-ref.schema.json",
  ".export-manifest.json": "export-manifest.schema.json"
};

const fixtureRoots = [
  join(root, "packages/core/fixtures"),
  join(root, "tests/fixtures")
];

let checked = 0;

for (const fixtureRoot of fixtureRoots) {
  const files = (await readdir(fixtureRoot)).filter((file) => file.endsWith(".json"));

  for (const file of files) {
    const suffix = Object.keys(schemaBySuffix).find((candidate) => file.endsWith(candidate));
    if (!suffix) {
      throw new Error(`${file}: no validation rule for fixture suffix`);
    }

    const schema = schemas.get(schemaBySuffix[suffix]);
    const value = await readJson(join(fixtureRoot, file));
    assertValid(file, schema, value, schemas);

    if (suffix === ".session.json") {
      assertSessionIntegrity(file, value);
      for (const event of value.events) {
        assertKnownPayloads(`${file} ${event.event_id}`, event, schemas);
      }
    }

    if (suffix === ".export-manifest.json") {
      for (const event of value.events) {
        assertKnownPayloads(`${file} ${event.event_id}`, event, schemas);
      }
    }

    checked += 1;
  }
}

console.log(`validate: ${checked} fixtures conform to current schemas`);
