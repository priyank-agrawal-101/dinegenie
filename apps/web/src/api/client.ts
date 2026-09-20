import type { ApiErrorResponse, BudgetBandsResponse, HealthResponse, MetadataResponse, RecommendationRequest, RecommendationResponse } from "./types";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "";

export class ApiError extends Error {
  constructor(
    message: string,
    readonly status: number,
    readonly requestId: string | null = null,
    readonly code = "UNKNOWN_ERROR",
    readonly details: Record<string, unknown> = {},
  ) {
    super(message);
    this.name = "ApiError";
  }
}

async function requestJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...init,
    signal: init?.signal
      ? AbortSignal.any([init.signal, AbortSignal.timeout(20_000)])
      : AbortSignal.timeout(20_000),
    headers: {
      Accept: "application/json",
      ...(init?.body ? { "Content-Type": "application/json" } : {}),
      ...init?.headers,
    },
  });

  const body: unknown = await response.json().catch(() => null);
  if (!response.ok) {
    const envelope = body as Partial<ApiErrorResponse> | null;
    const error = envelope?.error;
    throw new ApiError(
      "The request could not be completed.",
      response.status,
      response.headers.get("x-request-id") ?? error?.request_id ?? null,
      error?.code ?? (response.status === 429 ? "RATE_LIMITED" : "UNKNOWN_ERROR"),
      error?.details ?? {},
    );
  }

  if (body === null) throw new ApiError("Invalid response.", 502, null, "INVALID_RESPONSE");
  return body as T;
}

export function getLiveness(signal?: AbortSignal): Promise<HealthResponse> {
  return requestJson<HealthResponse>("/health/live", { signal });
}

export function getLocations(query: string, signal?: AbortSignal): Promise<MetadataResponse> {
  return requestJson(`/api/v1/metadata/locations?${new URLSearchParams({ query, limit: "50" })}`, { signal });
}

export function getCuisines(location: string, signal?: AbortSignal): Promise<MetadataResponse> {
  return requestJson(`/api/v1/metadata/cuisines?${new URLSearchParams({ location, limit: "250" })}`, { signal });
}

export function getBudgetBands(signal?: AbortSignal): Promise<BudgetBandsResponse> {
  return requestJson("/api/v1/metadata/budget-bands", { signal });
}

export async function createRecommendations(
  request: RecommendationRequest,
  signal?: AbortSignal,
): Promise<RecommendationResponse> {
  const response = await requestJson<RecommendationResponse>("/api/v1/recommendations", {
    method: "POST",
    body: JSON.stringify(request),
    signal,
  });
  const ids = response.recommendations?.map((item) => item.restaurant_id);
  if (!ids || new Set(ids).size !== ids.length || !response.meta?.dataset_version) {
    throw new ApiError("Invalid recommendation response.", 502, response.request_id, "INVALID_RESPONSE");
  }
  if (response.summary != null && (typeof response.summary !== "string" || response.summary.length > 500)) {
    throw new ApiError("Invalid summary response.", 502, response.request_id, "INVALID_RESPONSE");
  }
  return response;
}
