/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at https://mozilla.org/MPL/2.0/. */

export type RepresentationForm = "text" | "audio" | "notation" | "midi" | "data" | "morse" | "glyphs" | "code" | "other";
export type RepresentationRole = "subject" | "account" | "context" | "instruction" | "score" | "work";
export type Representation = {
  contract: "earworm/representation/v1";
  representation_id: string;
  subject_ref: string;
  form: RepresentationForm;
  media_type: string;
  encoding?: string;
  origin: {
    kind: "recorded" | "authored" | "generated" | "imported" | "transformed" | "unknown";
    domain: "acoustic" | "non_acoustic" | "mixed" | "unknown";
    source_refs: string[];
  };
  source_class: "recording" | "authored_work" | "conversation" | "correspondence" | "dataset" | "notation" | "code" | "generated_work" | "retained_execution" | "unknown" | "other";
  artifact: {
    state: "retained" | "reference_only" | "not_retained" | "withheld" | "unknown";
    ref?: string;
    sha256?: string;
    byte_count?: number;
    inline_text?: string;
  };
  preservation: { layout: "preserved" | "transformed" | "not_applicable"; losses: string[] };
  terms: { status: "declared" | "unknown"; ref?: string; reason?: string };
  convention: { status: "declared" | "unknown" | "not_applicable"; id?: string; revision?: string; reason?: string };
  time_basis: Array<{
    kind: "sequence" | "authored" | "source_event" | "capture" | "execution" | "unknown";
    unit?: string;
    clock_ref?: string;
    extent?: { start: number; end: number };
    reason?: string;
  }>;
};

export type RepresentationAccess = {
  contract: "earworm/representation-access/v1";
  access_id: string;
  operation_ref: string;
  representation_ref: string;
  role: RepresentationRole;
  status: "available" | "unavailable" | "withheld" | "unsupported";
  received_representation_ref?: string;
  coverage: {
    kind: "full" | "partial" | "none";
    unit: "byte" | "unicode_codepoint" | "sequence_index" | "sample" | "unknown";
    ranges: Array<{ start: number; end: number }>;
    omissions: string[];
  };
  binding_ref?: string;
  reason?: string;
};

export type RepresentationOutput = {
  contract: "earworm/representation-output/v1";
  output_id: string;
  operation_ref: string;
  kind: "account" | "work" | "prompt" | "event_log";
  representation_ref: string;
  completion: "complete" | "partial";
  authored_by: string[];
  input_access_refs: string[];
};

export type RepresentationRecord = {
  contract: "earworm/representation-record/v1";
  record_ref: string;
  operation_ref: string;
  representations: Representation[];
  accesses: RepresentationAccess[];
  relations: Array<{
    relation_id: string;
    kind: "transformed_from" | "account_of" | "response_to" | "performance_of";
    from_ref: string;
    to_ref: string;
    declared_by: string;
    method_ref?: string;
    losses?: string[];
  }>;
  outputs: RepresentationOutput[];
  binding_refs: Array<{
    binding_id: string;
    document_representation_ref: string;
    document_sha256: string;
    adoption_ref: string;
    application_ref: string;
    scope: { kind: "workspace" | "workflow" | "swarm" | "run" | "invocation"; ref: string };
    effective_at: string;
  }>;
  outcome: {
    status: "pending" | "completed" | "no_response" | "refused" | "withheld" | "failed" | "missing" | "source_only";
    recorded_by: string;
    reason: string;
  };
  return?: {
    previous_operation_ref: string;
    representation_ref: string;
    kind: "original" | "descendant";
    context_basis: "independent" | "informed" | "shared_analysis" | "unknown";
    context_access_refs: string[];
  };
};

export type RepresentationMeasurement = {
  contract: "earworm/representation-measurement/v1";
  measurement_id: string;
  representation_ref: string;
  method_ref: string;
  quantity: string;
  value: number;
  unit: string;
};
