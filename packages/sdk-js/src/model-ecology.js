import space from "@earworm/core/schemas/embedding-space.schema.json" with { type: "json" };
import evidence from "@earworm/core/schemas/analysis-evidence.schema.json" with { type: "json" };
import deployment from "@earworm/core/schemas/model-deployment.schema.json" with { type: "json" };
import { compileContractSchema, schemaErrors } from "./listening-contracts.js";
const validators = Object.fromEntries(Object.entries({"embedding-space":space,"analysis-evidence":evidence,"model-deployment":deployment}).map(([key, schema])=>[key,compileContractSchema(schema)]));
function finite(value) {
  if (typeof value === "number") return Number.isFinite(value);
  if (Array.isArray(value)) return value.every(finite);
  if (value && typeof value === "object") return Object.values(value).every(finite);
  return value === null || ["string", "boolean"].includes(typeof value);
}
export function modelEcologyErrors(name, value) {
  if (!Object.hasOwn(validators, name)) throw new Error("unknown ecology contract");
  if (!finite(value)) return ["value must contain finite JSON data"];
  const errors = schemaErrors(validators[name], value);
  if (!errors.length && name === "analysis-evidence" && value.view.end_seconds <= value.view.start_seconds) errors.push("analysis view must have positive duration");
  return errors;
}
