#!/usr/bin/env node
// Materialize the opt-in draft from the released schema and explicit evolution definitions.
import { readFile, writeFile } from "node:fs/promises";
const root = new URL("../packages/core/schemas/", import.meta.url);
const read = async (name) => JSON.parse(await readFile(new URL(name, root), "utf8"));
const schema = await read("akousma.schema.json");
const evolution = await read("record-evolution.schema.json");
const matterContext = await read("matter-context.schema.json");
const graph = await read("transformation-graph.schema.json");
delete graph.$id;
delete graph.$schema;
delete matterContext.$id;
delete matterContext.$schema;
function replaceContract(value) {
  if (Array.isArray(value)) return value.map(replaceContract);
  if (value && typeof value === "object") return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, replaceContract(item)]));
  return value === "earworm/auditum/v2" ? "earworm/auditum/v3" : value;
}
const next = replaceContract(schema);
next.$id = "https://earworm.dev/schemas/akousma-1.7.schema.json";
next.description = "Unreleased opt-in spec 1.7 / auditum v3. Generated from the released schema and record-evolution definitions. Legacy consumers must negotiate support or preserve opaquely; never silently downgrade.";
next.properties.schema_version = { const: "1.7.0" };
Object.assign(next.$defs, evolution.$defs);
next.$defs.matterContext = matterContext;
next.$defs.transformationGraph = graph;
const auditum = next.$defs.auditum;
auditum.anyOf = auditum.anyOf.filter((branch) => branch.properties.contract.const === "earworm/auditum/v3");
auditum.properties.contract = { const: "earworm/auditum/v3" };
// Revision-only artifact accounting; semantic validation restricts this to graph records.
auditum.anyOf.push({ required: ["revision", "route_decisions"], properties: Object.fromEntries(
  ["listenings", "route_decisions", "actions", "disagreements", "honest_absences"].map(key => [key, { type: "array", maxItems: 0 }])
) });
auditum.properties.listenings.description = "Attributable accounts; machine reports do not establish embodied hearing.";
auditum.properties.appeal = { $ref: "#/$defs/appeal" };
next.properties.lineage.properties.relations.items = { anyOf: [schema.properties.lineage.properties.relations.items, { $ref: "#/$defs/evolutionRelation" }] };
next.properties.record_kind = { enum: ["research_proposal", "generation_decision", "observation_account", "transformation_graph"] };
next.properties.extensions.properties = {
  earworm_research: { $ref: "#/$defs/research" },
  earworm_generation_decision: { $ref: "#/$defs/generationDecision" },
  earworm_observation: { $ref: "#/$defs/observationAccount" },
  earworm_matter_context: { $ref: "#/$defs/matterContext" },
  earworm_measurements: { $ref: "#/$defs/measurementSet" },
  earworm_agent_sector: { $ref: "#/$defs/agentSector" },
  earworm_transformation_graph: { $ref: "#/$defs/transformationGraph" }
};
for (const [kind, key] of [["research_proposal", "earworm_research"], ["generation_decision", "earworm_generation_decision"], ["observation_account", "earworm_observation"], ["transformation_graph", "earworm_transformation_graph"]]) {
  next.anyOf.push({ required: ["subject", "record_kind", "extensions"], properties: {
    record_kind: { const: kind }, extensions: { type: "object", required: [key] }
  } });
  (next.allOf ??= []).push({ if: { required: ["record_kind"], properties: { record_kind: { const: kind } } },
    then: { required: ["subject", "extensions"], properties: { extensions: { type: "object", required: [key] } } } });
}
const path = new URL("akousma-1.7.schema.json", root);
const content = JSON.stringify(next, null, 2) + "\n";
if (process.argv.includes("--check")) {
  if (await readFile(path, "utf8") !== content) throw new Error("Opt-in schema is stale; run node scripts/generate-next-schema.mjs");
} else await writeFile(path, content);
