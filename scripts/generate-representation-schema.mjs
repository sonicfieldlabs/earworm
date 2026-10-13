// Add an opt-in representation branch without changing the 1.8 source contract.
import { readFile, writeFile } from "node:fs/promises";

const root = new URL("../packages/core/schemas/", import.meta.url);
const schema = JSON.parse(await readFile(new URL("akousma-1.8.schema.json", root), "utf8"));
schema.$id = "https://earworm.dev/schemas/akousma-1.9.schema.json";
schema.description = "Opt-in spec 1.9: primary representations, actual access, completed works and declared return lineage. Consumer admission is required; existing records are not migrated implicitly.";
schema.properties.schema_version = { const: "1.9.0" };
schema.properties.record_kind.enum.push("representation_record");
schema.properties.extensions.properties.earworm_representation = {
  $ref: "https://earworm.dev/schemas/representation-record.schema.json"
};
schema.anyOf.push({
  required: ["subject", "record_kind", "extensions"],
  properties: {
    record_kind: { const: "representation_record" },
    extensions: { type: "object", required: ["earworm_representation"] }
  }
});
schema.allOf.push({
  if: { required: ["record_kind"], properties: { record_kind: { const: "representation_record" } } },
  then: { required: ["subject", "extensions"], properties: { extensions: { type: "object", required: ["earworm_representation"] } } }
});
const text = JSON.stringify(schema, null, 2) + "\n";
const path = new URL("akousma-1.9.schema.json", root);
if (process.argv.includes("--check")) {
  if (await readFile(path, "utf8") !== text) throw new Error("Spec 1.9 schema is stale");
} else await writeFile(path, text);
