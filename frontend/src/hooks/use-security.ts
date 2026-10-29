"use client";

import { keepPreviousData, useMutation, useQueryClient } from "@tanstack/react-query";

import { useQuery } from "@/lib/query";
import { api } from "@/lib/api";
import type {
  AiAnalysis,
  Alert,
  AlertDetail,
  AlertExplanation,
  AlertStatus,
  IncidentReport,
  Page,
  Rule,
  SecurityEvent,
  Severity,
  Upload,
} from "@/lib/types";

// --- Alerts ----------------------------------------------------------------------

export interface AlertFilters {
  severity?: Severity;
  status?: AlertStatus;
  rule_id?: string;
  src_ip?: string;
  q?: string;
  upload_id?: string;
  incident_id?: string;
  page: number;
  page_size: number;
}

export function useAlerts(filters: AlertFilters, enabled = true) {
  return useQuery({
    queryKey: ["alerts", filters],
    queryFn: () => api.get<Page<Alert>>("/alerts", { ...filters }),
    placeholderData: keepPreviousData,
    enabled,
  });
}

export function useAlert(id: string) {
  return useQuery({
    queryKey: ["alert", id],
    queryFn: () => api.get<AlertDetail>(`/alerts/${id}`),
  });
}

export function useRules() {
  return useQuery({
    queryKey: ["rules"],
    queryFn: () => api.get<Rule[]>("/alerts/rules"),
    staleTime: Infinity,
  });
}

function useInvalidateAlerts() {
  const qc = useQueryClient();
  return (id?: string) => {
    qc.invalidateQueries({ queryKey: ["alerts"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
    if (id) qc.invalidateQueries({ queryKey: ["alert", id] });
  };
}

export function useUpdateAlertStatus(id: string) {
  const invalidate = useInvalidateAlerts();
  return useMutation({
    mutationFn: (status: AlertStatus) => api.patch<Alert>(`/alerts/${id}`, { status }),
    onSuccess: () => invalidate(id),
  });
}

export function usePromoteAlert(id: string) {
  const invalidate = useInvalidateAlerts();
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api.post<{ incident_id: string; reference: string }>(`/alerts/${id}/promote`),
    onSuccess: () => {
      invalidate(id);
      qc.invalidateQueries({ queryKey: ["incidents"] });
    },
  });
}

// --- Events ----------------------------------------------------------------------

export interface EventFilters {
  category?: SecurityEvent["category"];
  outcome?: SecurityEvent["outcome"];
  username?: string;
  src_ip?: string;
  upload_id?: string;
  page: number;
  page_size: number;
}

export function useEvents(filters: EventFilters) {
  return useQuery({
    queryKey: ["events", filters],
    queryFn: () => api.get<Page<SecurityEvent>>("/events", { ...filters }),
    placeholderData: keepPreviousData,
  });
}

// --- Uploads ---------------------------------------------------------------------

export function useUploads(page: number) {
  return useQuery({
    queryKey: ["uploads", page],
    queryFn: () => api.get<Page<Upload>>("/uploads", { page, page_size: 10 }),
    placeholderData: keepPreviousData,
  });
}

export function useUploadLog() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (file: File) => api.upload<Upload>("/uploads", file),
    onSuccess: () => {
      for (const key of ["uploads", "alerts", "events", "dashboard"]) {
        qc.invalidateQueries({ queryKey: [key] });
      }
    },
  });
}

// --- AI --------------------------------------------------------------------------

export function useAiStatus() {
  return useQuery({
    queryKey: ["ai-status"],
    queryFn: () => api.get<{ enabled: boolean; provider: string; model: string }>("/ai/status"),
    staleTime: 5 * 60_000,
  });
}

export function useExplainAlert(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<AiAnalysis<AlertExplanation>>(`/ai/alerts/${id}/explain`),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["alert", id] }),
  });
}

export function useIncidentReport(incidentId: string) {
  return useQuery({
    queryKey: ["incident", incidentId, "ai-report"],
    queryFn: () => api.get<AiAnalysis<IncidentReport> | null>(`/ai/incidents/${incidentId}/report`),
  });
}

export function useGenerateIncidentReport(incidentId: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () =>
      api.post<AiAnalysis<IncidentReport>>(`/ai/incidents/${incidentId}/report`),
    onSuccess: (data) => qc.setQueryData(["incident", incidentId, "ai-report"], data),
  });
}
