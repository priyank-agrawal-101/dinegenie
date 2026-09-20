import type { BudgetBandsResponse, RecommendationResponse } from "../api/types";

export const budgetFixture: BudgetBandsResponse = { bands: [
  { id: "low", label: "Low", minimum_exclusive: null, maximum_inclusive: 600, currency: "INR", basis: "for_two" },
  { id: "medium", label: "Medium", minimum_exclusive: 600, maximum_inclusive: 1500, currency: "INR", basis: "for_two" },
  { id: "high", label: "High", minimum_exclusive: 1500, maximum_inclusive: null, currency: "INR", basis: "for_two" },
] };

export const recommendationFixture: RecommendationResponse = {
  request_id: "test-request-123",
  recommendations: [
    { restaurant_id: "spice", name: "Spice Elephant", location: "Banashankari", city: "Bengaluru",
      cuisines: ["Chinese", "North Indian", "Thai"], rating: 4.1,
      estimated_cost: { amount: 800, currency: "INR", basis: "for_two" },
      explanation: "Matches your Chinese preference, minimum rating and budget.",
      matched_preferences: ["Chinese", "minimum rating", "budget"], unverified_preferences: ["family-friendly"] },
    { restaurant_id: "jalsa", name: "Jalsa", location: "Banashankari", city: "Bengaluru",
      cuisines: ["Chinese", "North Indian"], rating: 4.1,
      estimated_cost: { amount: 800, currency: "INR", basis: "for_two" },
      explanation: "Fits your selected locality and budget.",
      matched_preferences: ["location", "budget"], unverified_preferences: [] },
  ],
  meta: { dataset_version: "fixture-v1", ranking_mode: "deterministic", filters_relaxed: [], candidate_count: 2, candidate_limit_applied: false },
};
