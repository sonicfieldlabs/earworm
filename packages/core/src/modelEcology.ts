/** Additive contracts. Existing AssetRef and AnalysisFrame remain authoritative. */
export interface EmbeddingSpace {
  model: string;
  revision: string;
  preprocessing_sha256: string;
  dimensions: number;
  pooling: string;
  metric: "cosine";
}
export interface AnalysisEvidence {
  contract: "earworm/analysis-evidence/v1";
  frame_id: string;
  deployment_id: string;
  model_revision: string;
  capability: string;
  view: {
    asset_id: string;
    content_sha256: string;
    start_seconds: number;
    end_seconds: number;
    sample_rate_hz: number;
    channels: number;
    transformations: string[];
  };
  evidence_kind: "measured" | "model_hypothesis" | "inferred" | "undetermined";
  confidence_kind: "not_provided" | "uncalibrated_score" | "calibrated_probability";
  result: Record<string, unknown>;
  limitations: string[];
}
export interface ModelDeployment {
  contract: "earworm/model-deployment/v1";
  id: string;
  owner: string;
  adapter: string;
  capabilities: string[];
  components: { id: string; revision: string; sha256: string }[];
  runtime_revision: string;
  license_review: string;
  validation_receipt: string;
  enabled: boolean;
  provisioned: boolean;
  max_input_seconds: number;
  max_output_seconds: number;
  measured_peak_memory_mib: number | null;
}
