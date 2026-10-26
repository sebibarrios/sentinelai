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

export interface DashboardSummary {
  range: "24h" | "7d" | "30d";
  open_incidents: number;
  critical_open_incidents: number;
  incidents_in_range: number;
  incidents_by_status: Record<IncidentStatus, number>;
  incidents_by_severity: Record<Severity, number>;
  recent_incidents: Incident[];
}
