import {
  LISTENING_ACCESS_CONTRACT, listeningAccessErrors, adaptListeningPasses,
  type ListeningAccess, type ListeningPassAdapterInput, type AuditumListening
} from "../packages/sdk-js/src/index.js";

const unknown = { status: "unknown", reason: "No declaration supplied." } as const;
const access: ListeningAccess = {
  contract: LISTENING_ACCESS_CONTRACT, declaration_id: "access:types", subject_ref: "asset:types",
  capture: unknown, sampled_representation: unknown, model_input: unknown, human_access: [unknown]
};
const errors: string[] = listeningAccessErrors(access);
const input: ListeningPassAdapterInput = { passes: [], participants: [], bindings: [] };
const listenings: AuditumListening[] = adaptListeningPasses(input).listenings;
void errors;
void listenings;
// @ts-expect-error Human access must be qualified, never a boolean.
const invalid: ListeningAccess["human_access"] = true;
void invalid;

import { claimValidityAt, claimRetentionAt, type ListeningClaimLifetime, type ListeningContext } from "../packages/sdk-js/src/index.js";
const lifetime: ListeningClaimLifetime = {
  claim_ref: "claim:types", listening_ref: "listening:types",
  validity: unknown, retention: unknown
};
claimValidityAt(lifetime, "2026-09-06T12:00:00Z");
claimRetentionAt(lifetime, "2026-09-06T12:00:00Z");
// @ts-expect-error Claim validity cannot be inferred from action authority.
const invalidValidity: ListeningClaimLifetime["validity"] = { expires_at: "2026-09-06T12:00:00Z" };
// @ts-expect-error A rendering declaration cannot be a boolean.
const invalidRendering: ListeningContext["contexts"][number]["report"]["human_rendering"] = false;
void invalidValidity;
void invalidRendering;

import { nextRecordErrors, nextRecordReferenceErrors, type NextAkousma, type AuditumAppeal } from "../packages/sdk-js/src/index.js";
declare const nextRecord: NextAkousma;
nextRecordErrors(nextRecord);
nextRecordReferenceErrors(nextRecord, []);
// @ts-expect-error Appeal states are workflow states, never scalar confidence.
const invalidAppeal: AuditumAppeal["status"] = 0.8;
void invalidAppeal;

import { createObservationAccount, matterContextErrors, type ObservationAccountOptions, type MatterContext } from "../packages/sdk-js/src/index.js";
declare const observationOptions: ObservationAccountOptions;
const observationAccount = createObservationAccount({}, observationOptions, () => []);
matterContextErrors({} as MatterContext, {}, observationOptions.access);
const observationKind: "research_proposal" | "generation_decision" | "observation_account" | "transformation_graph" | undefined = observationAccount.record_kind;
// @ts-expect-error Source modality does not declare an ultrasonic listening capability.
const unsupportedModality: MatterContext["source_modality"] = {status: "known", value: "ultrasound", evidence_refs: []};
void observationKind; void unsupportedModality;

import { compareMeasurementDescriptors, agentSectorView, type MeasurementDescriptor, type DescriptorComparisonOptions } from "../packages/sdk-js/src/index.js";
declare const comparisonOptions: DescriptorComparisonOptions;
const descriptorRelation = compareMeasurementDescriptors(observationAccount, observationAccount, comparisonOptions);
const sectorRendering = agentSectorView(observationAccount, "sector:test").renderings[0];
// @ts-expect-error Earworm's application mapping does not infer an arbitrary feature label.
const unsupportedFeature: MeasurementDescriptor["feature"] = "heard_similarity";
void descriptorRelation; void sectorRendering; void unsupportedFeature;

import { auditumView, createTransformationGraph, type TransformationMasaAdapter } from '../packages/sdk-js/src/index.js';
const auditView = auditumView('ak:test', { readRecord: () => null, readReceipt: () => null,
  canRead: () => false, supported_contracts: ['earworm/auditum-view/v1', 'earworm/forgetting-receipt/v1'] });
if (auditView.state === 'forgotten') {
  const deleted: true = auditView.receipt.record_deleted;
  void deleted;
  // @ts-expect-error Free-text receipt reasons are excluded from the projection.
  void auditView.receipt.reason;
}
const masaGraphAdapter: TransformationMasaAdapter = { validateMasa: () => [], lineageDirections: { 'masa:derived-from': 'subject-is-descendant' } };
void createTransformationGraph; void masaGraphAdapter;
// @ts-expect-error Permission callbacks must be synchronous booleans.
auditumView('ak:test', { readRecord: () => null, readReceipt: () => null, canRead: async () => true, supported_contracts: [] });

import { createGraphRecord, reviseGraphRecord, type GraphRevisionOptions } from '../packages/sdk-js/src/index.js';
declare const revisionOptions: GraphRevisionOptions;
const graphRecord = createGraphRecord({} as import('../packages/sdk-js/src/index.js').TransformationGraph,
  { created_at: '2026-09-06T12:00:00Z', originating_app: 'earworm', supported_contracts: [] }, masaGraphAdapter);
reviseGraphRecord(graphRecord, revisionOptions, masaGraphAdapter);
// @ts-expect-error Patch revisions require explicit new record identity and attribution.
reviseGraphRecord(graphRecord, { nodes: [] }, masaGraphAdapter);
