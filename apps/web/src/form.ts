import type { BudgetBand, RecommendationRequest } from "./api/types";

export interface FormValues {
  location: string;
  locationQuery: string;
  budget: BudgetBand | "custom";
  customMaximum: string;
  cuisines: string[];
  minimumRating: string;
  preferences: string;
  limit: string;
}

export const initialForm: FormValues = {
  location: "Indiranagar", locationQuery: "Indiranagar", budget: "medium", customMaximum: "",
  cuisines: ["Chinese", "North Indian", "Italian"], minimumRating: "4.0", preferences: "", limit: "3",
};

export type FormErrors = Partial<Record<keyof FormValues, string>>;

export function validateForm(form: FormValues, availableCuisines: string[]): FormErrors {
  const errors: FormErrors = {};
  if (!form.location || form.locationQuery.trim() !== form.location) {
    errors.location = "Choose a Bengaluru locality from the suggestions.";
  }
  const amount = Number(form.customMaximum);
  if (form.budget === "custom" && (!Number.isInteger(amount) || amount < 1 || amount > 100_000)) {
    errors.customMaximum = "Enter a whole amount from ₹1 to ₹1,00,000.";
  }
  if (form.cuisines.length > 10 || form.cuisines.some((value) => !availableCuisines.includes(value))) {
    errors.cuisines = "Choose up to 10 cuisines available in this locality.";
  }
  if (form.preferences.length > 300) errors.preferences = "Keep preferences within 300 characters.";
  return errors;
}

export function toRequest(form: FormValues): RecommendationRequest {
  return {
    location: form.location,
    budget: { band: form.budget === "custom" ? null : form.budget,
      max_amount: form.budget === "custom" ? Number(form.customMaximum) : null, currency: "INR" },
    cuisines: form.cuisines,
    minimum_rating: form.minimumRating === "any" ? null : Number(form.minimumRating),
    additional_preferences: form.preferences.trim() || null,
    limit: Number(form.limit),
  };
}

export function summaryOf(request: RecommendationRequest): string {
  const budget = request.budget.max_amount !== null
    ? `up to ₹${request.budget.max_amount.toLocaleString("en-IN")} for two`
    : `${request.budget.band} budget`;
  return [request.location, budget, request.cuisines.join(" or ") || "any cuisine",
    request.minimum_rating === null ? "any rating" : `${request.minimum_rating.toFixed(1)}+ rating`].join(" · ");
}
