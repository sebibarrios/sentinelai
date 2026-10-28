"use client";

import {
  useQuery as useTanstackQuery,
  type QueryKey,
  type UseQueryOptions,
  type UseQueryResult,
} from "@tanstack/react-query";

import { useHydrated } from "@/hooks/use-hydrated";

/**
 * Drop-in replacement for TanStack Query's useQuery that is safe to hydrate.
 *
 * Next.js streams the server HTML and React hydrates parts of the page at slightly
 * different moments. If one part (say the header) fetches the current user and the
 * request finishes before another part (the page) hydrates, that page would read the
 * cached user on its first render, render role-based buttons the server never
 * rendered, and React would throw a hydration mismatch. This bug is timing-dependent
 * and was caught by the end-to-end tests' console guard.
 *
 * Here, every query reports "pending" during hydration, exactly as the server saw
 * it, and re-renders with real data immediately after. Fetching is unaffected.
 */
export function useQuery<
  TQueryFnData = unknown,
  TError = Error,
  TData = TQueryFnData,
  TQueryKey extends QueryKey = QueryKey,
>(options: UseQueryOptions<TQueryFnData, TError, TData, TQueryKey>): UseQueryResult<TData, TError> {
  const result = useTanstackQuery(options);
  const hydrated = useHydrated();
  if (hydrated) return result;
  return {
    ...result,
    data: undefined,
    error: null,
    status: "pending",
    isPending: true,
    isLoading: true,
    isSuccess: false,
    isError: false,
    isPlaceholderData: false,
  } as unknown as UseQueryResult<TData, TError>;
}
