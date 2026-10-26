"use client";

import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { api } from "@/lib/api";
import type {
  DashboardSummary,
  HistoryEntry,
  Incident,
  IncidentDetail,
  IncidentStatus,
  Note,
  Page,
  Severity,
  UserBrief,
} from "@/lib/types";

export interface IncidentFilters {
  status?: IncidentStatus;
  severity?: Severity;
  q?: string;
  page: number;
  page_size: number;
}

export interface IncidentInput {
  title?: string;
  description?: string;
  severity?: Severity;
  status?: IncidentStatus;
  assignee_id?: string | null;
}

export function useIncidents(filters: IncidentFilters) {
  return useQuery({
    queryKey: ["incidents", filters],
    queryFn: () => api.get<Page<Incident>>("/incidents", { ...filters }),
    placeholderData: keepPreviousData, // keep the table steady while the next page loads
  });
}

export function useIncident(id: string) {
  return useQuery({
    queryKey: ["incident", id],
    queryFn: () => api.get<IncidentDetail>(`/incidents/${id}`),
  });
}

export function useIncidentHistory(id: string) {
  return useQuery({
    queryKey: ["incident", id, "history"],
    queryFn: () => api.get<HistoryEntry[]>(`/incidents/${id}/history`),
  });
}

export function useAssignableUsers(enabled: boolean) {
  return useQuery({
    queryKey: ["users", "assignable"],
    queryFn: () => api.get<UserBrief[]>("/users/assignable"),
    enabled,
    staleTime: 5 * 60_000,
  });
}

export function useDashboard(range: DashboardSummary["range"]) {
  return useQuery({
    queryKey: ["dashboard", range],
    queryFn: () => api.get<DashboardSummary>("/dashboard/summary", { range }),
  });
}

function useInvalidateIncidents() {
  const qc = useQueryClient();
  return (id?: string) => {
    qc.invalidateQueries({ queryKey: ["incidents"] });
    qc.invalidateQueries({ queryKey: ["dashboard"] });
    if (id) qc.invalidateQueries({ queryKey: ["incident", id] });
  };
}

export function useCreateIncident() {
  const invalidate = useInvalidateIncidents();
  return useMutation({
    mutationFn: (body: IncidentInput) => api.post<Incident>("/incidents", body),
    onSuccess: () => invalidate(),
  });
}

export function useUpdateIncident(id: string) {
  const invalidate = useInvalidateIncidents();
  return useMutation({
    mutationFn: (body: IncidentInput) => api.patch<Incident>(`/incidents/${id}`, body),
    onSuccess: () => invalidate(id),
  });
}

export function useAddNote(id: string) {
  const invalidate = useInvalidateIncidents();
  return useMutation({
    mutationFn: (body: string) => api.post<Note>(`/incidents/${id}/notes`, { body }),
    onSuccess: () => invalidate(id),
  });
}
