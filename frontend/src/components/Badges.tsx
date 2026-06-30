import type { Intent, RiskLevel } from "../types";

const INTENT_LABEL: Record<Intent, string> = {
  instruction: "Instruction",
  warning: "Warning",
  question: "Question",
  confirmation: "Confirmation",
  emergency: "Emergency",
  approval: "Approval",
  escalation: "Escalation",
  statement: "Statement",
};

export function IntentBadge({ intent }: { intent: Intent }) {
  return <span className={`badge intent intent-${intent}`}>{INTENT_LABEL[intent]}</span>;
}

const RISK_LABEL: Record<RiskLevel, string> = {
  none: "No risk",
  low: "Low risk",
  medium: "Medium risk",
  high: "High risk",
  critical: "Critical",
};

export function RiskBadge({ level }: { level: RiskLevel }) {
  if (level === "none") return null;
  return <span className={`badge risk risk-${level}`}>⚠ {RISK_LABEL[level]}</span>;
}
