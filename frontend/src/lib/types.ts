// Mirrors the backend's Pydantic response models (backend/app/schemas).

export type Role = "admin" | "analyst" | "viewer";
export type Severity = "low" | "medium" | "high" | "critical";
export type IncidentStatus = "open" | "investigating" | "contained" | "resolved" | "closed";

export const SEVERITIES: Severity[] = ["critical", "high", "medium", "low"];
export const INCIDENT_STATUSES: IncidentStatus[] = [
  "open",
  "investigating",
  "contained",
  "resolved",
  "closed",
];

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface UserBrief {
  id: string;
  full_name: string;
  email: string;
}

export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
}

export interface Incident {
  id: string;
  reference: string;
  title: string;
  description: string;
  severity: Severity;
  status: IncidentStatus;
  assignee: UserBrief | null;
  created_by: UserBrief;
  created_at: string;
  updated_at: string;
  closed_at: string | null;
}

export interface Note {
  id: string;
  body: string;
  created_at: string;
  author: UserBrief;
}

export interface IncidentDetail extends Incident {
  notes: Note[];
}

export interface HistoryEntry {
  id: number;
  action:
    | "created"
    | "updated"
    | "assigned"
    | "status_changed"
    | "note_added"
    | "alert_linked";
  field: string | null;
  old_value: string | null;
  new_value: string | null;
  created_at: string;
  actor: UserBrief;
}

export interface DashboardSummary extends DashboardAlerts {
  range: "24h" | "7d" | "30d";
  open_incidents: number;
  critical_open_incidents: number;
  incidents_in_range: number;
  incidents_by_status: Record<IncidentStatus, number>;
  incidents_by_severity: Record<Severity, number>;
  recent_incidents: Incident[];
}

// --- Phase 4: uploads, events, alerts, AI -----------------------------------------

export type AlertStatus = "open" | "acknowledged" | "dismissed" | "escalated";
export const ALERT_STATUSES: AlertStatus[] = ["open", "acknowledged", "dismissed", "escalated"];

export interface Upload {
  id: string;
  original_filename: string;
  format: "csv" | "json";
  size_bytes: number;
  status: "processing" | "completed" | "failed";
  rows_total: number;
  rows_parsed: number;
  rows_rejected: number;
  alerts_created: number;
  rejection_samples: { line: number; reason: string }[];
  processing_ms: number | null;
  uploaded_by: UserBrief;
  created_at: string;
  completed_at: string | null;
}

export interface SecurityEvent {
  id: number;
  upload_id: string;
  occurred_at: string;
  category: "auth" | "network";
  action: string;
  outcome: "success" | "failure" | "allowed" | "denied";
  username: string | null;
  src_ip: string;
  dst_ip: string | null;
  dst_port: number | null;
  protocol: string | null;
  user_agent: string | null;
  country: string | null;
}

export interface Alert {
  id: string;
  rule_id: string;
  rule_name: string;
  title: string;
  severity: Severity;
  status: AlertStatus;
  src_ip: string | null;
  username: string | null;
  first_seen: string;
  last_seen: string;
  event_count: number;
  details: Record<string, unknown>;
  upload_id: string;
  incident_id: string | null;
  created_at: string;
}

export interface AiAnalysis<T = unknown> {
  id: string;
  kind: "alert_explanation" | "incident_report";
  model: string;
  prompt_version: string;
  output: T;
  requested_by: UserBrief;
  created_at: string;
  cached?: boolean;
}

export interface AlertExplanation {
  summary: string;
  explanation: string;
  likely_tactics: string[];
  investigation_steps: { step: string; rationale: string }[];
  recommended_severity: Severity;
  confidence: "low" | "medium" | "high";
  caveats: string[];
}

export interface IncidentReport {
  executive_summary: string;
  timeline: { time: string; event: string }[];
  affected_accounts: string[];
  indicators: { type: "ip" | "username" | "port" | "other"; value: string; context: string }[];
  impact_assessment: string;
  containment_steps: string[];
  recommendations: string[];
  open_questions: string[];
  caveats: string[];
  ungrounded_indicators_removed?: number;
}

export interface AlertDetail extends Alert {
  rule_description: string;
  evidence: SecurityEvent[];
  evidence_truncated: boolean;
  ai_analysis: AiAnalysis<AlertExplanation> | null;
}

export interface Rule {
  id: string;
  name: string;
  description: string;
  severity: Severity;
}

export interface TimelinePoint extends Record<Severity, number> {
  bucket: string;
}

export interface DashboardAlerts {
  open_alerts: number;
  open_alerts_by_severity: Record<Severity, number>;
  alerts_in_range: number;
  events_in_range: number;
  alert_timeline: TimelinePoint[];
  top_sources: { ip: string; alerts: number; max_severity: Severity }[];
  recent_alerts: Alert[];
}
