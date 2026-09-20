import { afterEach, describe, expect, it, vi } from "vitest";
import { createRecommendations } from "./client";
import { initialForm, toRequest } from "../form";
import { recommendationFixture } from "../test/fixtures";

afterEach(() => vi.unstubAllGlobals());
describe("API client", () => {
  it("retains stable error codes, field paths and request IDs", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: {
      code: "VALIDATION_ERROR", request_id: "body-id", details: { fields: [{ path: "body.budget" }] },
    } }), { status: 422, headers: { "x-request-id": "trusted-id" } })));
    await expect(createRecommendations(toRequest(initialForm))).rejects.toMatchObject({
      code: "VALIDATION_ERROR", status: 422, requestId: "trusted-id", details: { fields: [{ path: "body.budget" }] },
    });
  });
  it("handles a non-JSON gateway failure safely", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response("private stack trace", { status: 502 })));
    await expect(createRecommendations(toRequest(initialForm))).rejects.toMatchObject({ message: "The request could not be completed.", status: 502 });
  });
  it("rejects duplicate result identities", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(new Response(JSON.stringify({ ...recommendationFixture,
      recommendations: [recommendationFixture.recommendations[0], recommendationFixture.recommendations[0]],
    }))));
    await expect(createRecommendations(toRequest(initialForm))).rejects.toMatchObject({ code: "INVALID_RESPONSE" });
  });
});
