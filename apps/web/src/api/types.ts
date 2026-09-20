export interface HealthResponse {
  status: "alive";
  service: string;
  version: string;
  environment: string;
}

export type BudgetBand = "low" | "medium" | "high";

export interface BudgetInput {
  band: BudgetBand | null;
  max_amount: number | null;
  currency: "INR";
}

export interface RecommendationRequest {
  location: string;
  budget: BudgetInput;
  cuisines: string[];
  minimum_rating: number | null;
  additional_preferences: string | null;
  limit: number;
}

export interface Money {
  amount: number;
  currency: string;
  basis: "for_two" | "per_person" | "unknown";
}

export interface Recommendation {
  restaurant_id: string;
  name: string;
  location: string;
  city: string;
  cuisines: string[];
  rating: number | null;
  estimated_cost: Money | null;
  explanation: string;
  matched_preferences: string[];
  unverified_preferences: string[];
}

export type RankingMode = "deterministic" | "llm_assisted" | "deterministic_fallback";

export interface RecommendationResponse {
  request_id: string;
  recommendations: Recommendation[];
  summary?: string | null;
  meta: {
    dataset_version: string;
    ranking_mode: RankingMode;
    filters_relaxed: string[];
    candidate_count: number;
    candidate_limit_applied: boolean;
  };
}

export interface ApiErrorResponse {
  error: {
    code: string;
    message: string;
    request_id: string;
    details?: Record<string, unknown>;
  };
}

export interface MetadataResponse {
  dataset_version: string;
  values: string[];
}

export interface BudgetBandDefinition {
  id: BudgetBand;
  label: string;
  minimum_exclusive: number | null;
  maximum_inclusive: number | null;
  currency: "INR";
  basis: "for_two";
}

export interface BudgetBandsResponse { bands: BudgetBandDefinition[] }
