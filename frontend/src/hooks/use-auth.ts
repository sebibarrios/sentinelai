"use client";

import { useMutation, useQueryClient } from "@tanstack/react-query";

import { useRouter } from "next/navigation";

import { useQuery } from "@/lib/query";
import { api, ApiError } from "@/lib/api";
import type { Role, User } from "@/lib/types";

const ROLE_LEVEL: Record<Role, number> = { viewer: 1, analyst: 2, admin: 3 };

export function useMe() {
  return useQuery({
    queryKey: ["me"],
    queryFn: () => api.get<User>("/auth/me"),
    staleTime: 60_000,
  });
}

/** UI-only role check for hiding controls. The backend is the real security boundary. */
export function useCan(minimum: Role): boolean {
  const { data } = useMe();
  return !!data && ROLE_LEVEL[data.role] >= ROLE_LEVEL[minimum];
}

/** Caller decides where to navigate after sign-in (e.g. back to the page that required it). */
export function useLogin() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { email: string; password: string }) =>
      api.post<User>("/auth/login", body),
    onSuccess: (user) => qc.setQueryData(["me"], user),
  });
}

export function useRegister() {
  const qc = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: (body: { email: string; password: string; full_name: string }) =>
      api.post<User>("/auth/register", body),
    onSuccess: (user) => {
      qc.setQueryData(["me"], user);
      router.replace("/dashboard");
    },
  });
}

export function useLogout() {
  const qc = useQueryClient();
  const router = useRouter();
  return useMutation({
    mutationFn: () => api.post<void>("/auth/logout"),
    onSettled: () => {
      qc.clear();
      router.replace("/login");
    },
  });
}

export function isUnauthorized(error: unknown): boolean {
  return error instanceof ApiError && error.status === 401;
}
