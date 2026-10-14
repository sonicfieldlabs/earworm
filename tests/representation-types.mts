import { type Representation, type RepresentationOutput, type RepresentationRecord } from "../packages/sdk-js/src/index.js";
import { representationRecordErrors, admitRepresentationRecord, REPRESENTATION_CONTRACTS } from "../packages/sdk-js/src/index.js";

const material: Representation = {
  contract: "earworm/representation/v1", representation_id: "r", subject_ref: "s", form: "text", media_type: "text/plain", encoding: "utf-8",
  origin: { kind: "authored", domain: "non_acoustic", source_refs: [] }, source_class: "authored_work",
  artifact: { state: "retained", ref: "object", sha256: "a".repeat(64), byte_count: 0 },
  preservation: { layout: "preserved", losses: [] }, terms: { status: "declared", ref: "terms" },
  convention: { status: "not_applicable" }, time_basis: [{ kind: "sequence" }]
};
const work: RepresentationOutput = {
  contract: "earworm/representation-output/v1", output_id: "w", operation_ref: "op", kind: "work", representation_ref: "r",
  completion: "complete", authored_by: ["writer"], input_access_refs: ["access"]
};
// @ts-expect-error representation forms are negotiated labels, not arbitrary strings
material.form = "frequency-range";
// @ts-expect-error a completed output has an explicit work/account/prompt/event role
work.kind = "whatever";
// @ts-expect-error adoption is not a representation role named permission
const role: import("../packages/sdk-js/src/index.js").RepresentationRole = "permission";
declare const record: RepresentationRecord;
representationRecordErrors(record);
const admitted: RepresentationRecord = admitRepresentationRecord(record, { supportedContracts: REPRESENTATION_CONTRACTS, resolveArtifact: () => new Uint8Array() });
void admitted;
