import { useCallback, useEffect, useState } from "react";
import { getBudgetBands, getCuisines, getLocations } from "../api/client";
import type { BudgetBandsResponse, MetadataResponse } from "../api/types";

type Resource<T> =
  | { key: string; status: "ready"; data: T }
  | { key: string; status: "error" | "loading"; data?: undefined };

// A response can only populate the query that requested it.
function useResource<T>(key: string, enabled: boolean, load: (signal: AbortSignal) => Promise<T>, delay = 0) {
  const [resource, setResource] = useState<Resource<T>>({ key: "", status: "loading" });
  useEffect(() => {
    if (!enabled) return;
    const controller = new AbortController();
    const timer = window.setTimeout(() => {
      load(controller.signal).then(
        (data) => { if (!controller.signal.aborted) setResource({ key, status: "ready", data }); },
        () => { if (!controller.signal.aborted) setResource({ key, status: "error" }); },
      );
    }, delay);
    return () => { window.clearTimeout(timer); controller.abort(); };
  }, [key, enabled, load, delay]);
  return resource.key === key ? resource : { key, status: "loading" as const, data: undefined };
}

export function useLocations(query: string, retry: number) {
  const load = useCallback((signal: AbortSignal) => getLocations(query, signal), [query]);
  return useResource<MetadataResponse>(`${query}:${retry}`, true, load, 150);
}

export function useCuisines(location: string, retry: number) {
  const load = useCallback((signal: AbortSignal) => getCuisines(location, signal), [location]);
  return useResource<MetadataResponse>(`${location}:${retry}`, Boolean(location), load);
}

const loadBands = (signal: AbortSignal) => getBudgetBands(signal);
export function useBudgetBands(retry: number) {
  return useResource<BudgetBandsResponse>(String(retry), true, loadBands);
}
