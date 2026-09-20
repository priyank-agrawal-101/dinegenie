import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { RestaurantCard } from "./RestaurantCard";
import { recommendationFixture } from "../test/fixtures";

describe("RestaurantCard", () => {
  it("separates verified and unverified facts and preserves missing values", () => {
    render(<ol><RestaurantCard rank={1} restaurant={{ ...recommendationFixture.recommendations[0], rating: null, estimated_cost: null, cuisines: [] }} /></ol>);
    expect(screen.getByText("Rating unavailable")).toBeVisible();
    expect(screen.getByText("Estimated cost unavailable")).toBeVisible();
    expect(screen.getByText("Cuisine unavailable")).toBeVisible();
    expect(screen.getByRole("heading", { name: "Not verified by the dataset" })).toBeVisible();
  });
  it("escapes source text and formats the returned currency and basis", () => {
    const name = '<script>alert("source")</script>';
    render(<ol><RestaurantCard rank={1} restaurant={{ ...recommendationFixture.recommendations[0], name,
      estimated_cost: { amount: 20, currency: "USD", basis: "unknown" } }} /></ol>);
    expect(screen.getByRole("heading", { name })).toBeVisible();
    expect(document.querySelector("script")).toBeNull();
    expect(screen.getByText(/20.00/)).toBeVisible();
    expect(screen.getByText("Estimated cost · basis unavailable")).toBeVisible();
    expect(screen.queryByText("Estimated cost for two")).not.toBeInTheDocument();
  });
});
