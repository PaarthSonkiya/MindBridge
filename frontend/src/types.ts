export type Language = "en" | "vi";
export type Expertise = "engineer" | "technician" | "operator" | "trainee";

export type Intent =
  | "instruction"
  | "warning"
  | "question"
  | "confirmation"
  | "emergency"
  | "approval"
  | "escalation"
  | "statement";

export type RiskLevel = "none" | "low" | "medium" | "high" | "critical";

export interface RiskAssessment {
  level: RiskLevel;
  requires_confirmation: boolean;
  hazards: string[];
  rationale: string;
}

export interface ProcessResponse {
  session_id: string;
  original_text: string;
  translation: string;
  intent: Intent;
  risk: RiskAssessment;
  adapted_message: string;
  key_points: string[];
  requires_readback: boolean;
  engine: string;
}

export interface UnderstandingFactor {
  name: string;
  score: number;
  detail: string;
}

export interface VerifyResponse {
  session_id: string;
  understanding_score: number;
  understood: boolean;
  factors: UnderstandingFactor[];
  missing_points: string[];
  follow_up: string;
  engine: string;
}

export interface HandoverResponse {
  session_id: string;
  generated_at: string;
  summary: string;
  completed_tasks: string[];
  pending_issues: string[];
  safety_observations: string[];
  equipment_referenced: string[];
  engine: string;
}

export interface Health {
  status: string;
  version: string;
  engine: string;
  llm_enabled: boolean;
}
