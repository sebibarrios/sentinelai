"use client";

import { useSyncExternalStore } from "react";

const subscribe = () => () => {};

/**
 * False on the server and during hydration; true once the client has taken over.
 *
 * React uses the server snapshot (false) while hydrating, so anything rendered
 * behind this flag matches the server HTML exactly, then re-renders on the client.
 */
export function useHydrated(): boolean {
  return useSyncExternalStore(
    subscribe,
    () => true,
    () => false,
  );
}
