import { act, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { App } from "./App";
import { ApiError, createRecommendations, getBudgetBands, getCuisines, getLocations } from "./api/client";
import { budgetFixture, recommendationFixture } from "./test/fixtures";

vi.mock("./api/client", async (original) => {
  const actual = await original<typeof import("./api/client")>();
  return { ...actual, createRecommendations: vi.fn(), getBudgetBands: vi.fn(), getCuisines: vi.fn(), getLocations: vi.fn() };
});

beforeEach(() => {
  vi.resetAllMocks();
  vi.mocked(getBudgetBands).mockResolvedValue(budgetFixture);
  vi.mocked(getLocations).mockResolvedValue({ dataset_version: "fixture-v1", values: ["Banashankari", "Basavanagudi"] });
  vi.mocked(getCuisines).mockResolvedValue({ dataset_version: "fixture-v1", values: ["Chinese", "Italian", "Thai"] });
  vi.mocked(createRecommendations).mockResolvedValue(recommendationFixture);
});

async function selectLocality(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole("combobox", { name: /Location/ }));
  await user.click(await screen.findByRole("option", { name: /Banashankari/ }));
  await screen.findByRole("checkbox", { name: "Chinese" });
  await waitFor(() => expect(screen.getByRole("button", { name: /Find Restaurants/i })).toBeEnabled());
}

describe("restaurant search", () => {
  it.each(["llm_assisted", "deterministic_fallback"] as const)("renders %s safely using the same cards", async (mode) => {
    vi.mocked(createRecommendations).mockResolvedValueOnce({ ...recommendationFixture,
      meta: { ...recommendationFixture.meta, ranking_mode: mode }, summary: "Source-checked shortlist.",
    });
    const user = userEvent.setup();
    render(<App />);
    await selectLocality(user);
    await user.click(screen.getByRole("button", { name: /Find Restaurants/i }));
    await screen.findByRole("heading", { name: "2 restaurants match your preferences" });
    expect(screen.getAllByRole("article")).toHaveLength(2);
    if (mode === "llm_assisted") {
      expect(screen.getByText("Source-checked shortlist.")).toBeVisible();
      expect(screen.getByText(/AI-assisted ordering/)).toBeVisible();
    } else {
      expect(screen.getByText(/AI assistance is unavailable/)).toBeVisible();
      expect(screen.queryByText("Source-checked shortlist.")).not.toBeInTheDocument();
    }
  });
  it("validates required locality and a missing custom maximum", async () => {
    const user = userEvent.setup();
    render(<App />);
    await waitFor(() => expect(screen.getByRole("button", { name: /Find Restaurants/i })).toBeEnabled());
    await user.clear(screen.getByRole("combobox", { name: /Location/ }));
    await user.click(screen.getByRole("button", { name: /Find Restaurants/i }));
    expect(screen.getByText("Choose a Bengaluru locality from the suggestions.")).toBeVisible();
    expect(createRecommendations).not.toHaveBeenCalled();
    await selectLocality(user);
    await user.click(screen.getByLabelText("Set my own maximum"));
    await user.click(screen.getByRole("button", { name: /Find Restaurants/i }));
    expect(screen.getByText("Enter a whole amount from ₹1 to ₹1,00,000.")).toBeVisible();
    expect(createRecommendations).not.toHaveBeenCalled();
  });

  it("submits typed preferences and preserves backend ordering and inputs", async () => {
    const user = userEvent.setup();
    render(<App />);
    await selectLocality(user);
    await user.click(screen.getByRole("checkbox", { name: "Chinese" }));
    await user.selectOptions(screen.getByLabelText("Minimum rating"), "4.0");
    await user.type(screen.getByLabelText(/Additional preferences/), "family-friendly");
    await user.click(screen.getByRole("button", { name: /Find Restaurants/i }));
    await screen.findByRole("heading", { name: "2 restaurants match your preferences" });
    expect(vi.mocked(createRecommendations).mock.calls[0][0]).toEqual({
      location: "Banashankari", budget: { band: "medium", max_amount: null, currency: "INR" },
      cuisines: ["Chinese"], minimum_rating: 4, additional_preferences: "family-friendly", limit: 3,
    });
    expect(screen.getAllByRole("article").map((article) => article.querySelector("h3")?.textContent)).toEqual(["Spice Elephant", "Jalsa"]);
    expect(screen.getByRole("checkbox", { name: "Chinese" })).toBeChecked();
    expect(screen.getByLabelText(/Additional preferences/)).toHaveValue("family-friendly");
    expect(screen.getByText("Not verified by the dataset")).toBeVisible();
  });

  it("cancels pending work on an edit and ignores a late response", async () => {
    let resolveRequest!: (value: typeof recommendationFixture) => void;
    vi.mocked(createRecommendations).mockImplementation(() => new Promise((resolve) => { resolveRequest = resolve; }));
    const user = userEvent.setup();
    render(<App />);
    await selectLocality(user);
    await user.dblClick(screen.getByRole("button", { name: /Find Restaurants/i }));
    expect(createRecommendations).toHaveBeenCalledTimes(1);
    expect(screen.getByRole("heading", { name: "Building your shortlist" })).toBeVisible();
    await user.selectOptions(screen.getByLabelText("Minimum rating"), "4.5");
    expect(vi.mocked(createRecommendations).mock.calls[0][1]?.aborted).toBe(true);
    await act(async () => resolveRequest(recommendationFixture));
    expect(screen.queryByRole("heading", { name: "Spice Elephant" })).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Find Restaurants/i })).toBeEnabled();
  });

  it("submits a custom maximum without a budget band and labels a single result", async () => {
    vi.mocked(createRecommendations).mockResolvedValueOnce({ ...recommendationFixture, recommendations: [recommendationFixture.recommendations[0]] });
    const user = userEvent.setup();
    render(<App />);
    await selectLocality(user);
    await user.click(screen.getByLabelText("Set my own maximum"));
    await user.type(screen.getByLabelText("Maximum amount in INR"), "900");
    await user.selectOptions(screen.getByLabelText("Number of results"), "1");
    await user.click(screen.getByRole("button", { name: /Find Restaurants/i }));
    await screen.findByRole("heading", { name: "1 restaurant matches your preferences" });
    expect(screen.getByRole("link", { name: /View 1 result/ })).toBeVisible();
    expect(vi.mocked(createRecommendations).mock.calls[0][0]).toMatchObject({ budget: { band: null, max_amount: 900, currency: "INR" }, limit: 1 });
  });

  it("shows backend budget validation for a selected band", async () => {
    vi.mocked(createRecommendations).mockRejectedValueOnce(new ApiError("bad", 422, null, "VALIDATION_ERROR", { fields: [{ path: "body.budget.band" }] }));
    const user = userEvent.setup();
    render(<App />);
    await selectLocality(user);
    await user.click(screen.getByRole("button", { name: /Find Restaurants/i }));
    expect(await screen.findByText("Please review this value and try again.")).toBeVisible();
  });

  it("keeps failed locality metadata retry reachable by keyboard", async () => {
    vi.mocked(getLocations).mockRejectedValueOnce(new Error("offline"));
    const user = userEvent.setup();
    render(<App />);
    await user.click(screen.getByRole("combobox", { name: /Location/ }));
    const retry = await screen.findByRole("button", { name: "Retry localities" });
    await user.tab();
    expect(retry).toHaveFocus();
    await user.keyboard("{Enter}");
    expect(await screen.findByRole("option", { name: /Banashankari/ })).toBeVisible();
  });

  it("requires an explicit search after accepting a refinement", async () => {
    vi.mocked(createRecommendations).mockRejectedValueOnce(new ApiError("No matches", 404, "empty-id", "NO_MATCHES"));
    const user = userEvent.setup();
    render(<App />);
    await selectLocality(user);
    await user.click(screen.getByRole("checkbox", { name: "Chinese" }));
    await user.click(screen.getByRole("button", { name: /Find Restaurants/i }));
    await screen.findByRole("heading", { name: "No exact matches this time." });
    expect(screen.getByRole("checkbox", { name: "Chinese" })).toBeChecked();
    await user.click(screen.getByRole("button", { name: "Try any cuisine" }));
    expect(screen.getByRole("checkbox", { name: "Chinese" })).not.toBeChecked();
    expect(createRecommendations).toHaveBeenCalledTimes(1);
    await user.click(screen.getByRole("button", { name: /Find Restaurants/i }));
    await screen.findByRole("heading", { name: "2 restaurants match your preferences" });
    expect(vi.mocked(createRecommendations).mock.calls[1][0].cuisines).toEqual([]);
  });

  it.each([
    [new ApiError("bad", 422, null, "VALIDATION_ERROR", { fields: [{ path: "body.location" }] }), /Some preferences could not be accepted/],
    [new ApiError("unavailable", 503, null, "DATASET_UNAVAILABLE"), /Restaurant data is temporarily unavailable/],
    [new ApiError("limited", 429, null, "RATE_LIMITED"), /too many requests/],
    [new Error("offline"), /couldn't reach the recommendation service/],
  ])("preserves inputs and provides recovery after %s", async (error, message) => {
    vi.mocked(createRecommendations).mockRejectedValueOnce(error);
    const user = userEvent.setup();
    render(<App />);
    await selectLocality(user);
    await user.click(screen.getByRole("button", { name: /Find Restaurants/i }));
    expect(await screen.findByText(message)).toBeVisible();
    expect(screen.getByRole("combobox", { name: /Location/ })).toHaveValue("Banashankari");
    await user.click(screen.getByRole("button", { name: "Try search again" }));
    await screen.findByRole("heading", { name: "2 restaurants match your preferences" });
  });

  it("recovers failed metadata without discarding the form", async () => {
    vi.mocked(getBudgetBands).mockRejectedValueOnce(new Error("offline"));
    const user = userEvent.setup();
    render(<App />);
    await user.click(await screen.findByRole("button", { name: "Retry options" }));
    await screen.findByRole("radio", { name: /Medium/ });
    expect(screen.getByRole("combobox", { name: /Location/ })).toBeVisible();
  });
});
