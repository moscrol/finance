import { afterEach, describe, expect, it, vi } from "vitest";
import { getCredits } from "./api";

describe("api error surfacing", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("unwraps FastAPI's {detail} so the user sees the sentence, not the JSON", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(
        new Response(
          JSON.stringify({ detail: "研究额度已用完（剩余 0 次）。请联系管理员充值" }),
          { status: 429, headers: { "Content-Type": "application/json" } },
        ),
      ),
    );
    await expect(getCredits("u1")).rejects.toThrow(
      "研究额度已用完（剩余 0 次）。请联系管理员充值",
    );
  });

  it("falls back to the raw body or status text when the body is not {detail}", async () => {
    vi.stubGlobal(
      "fetch",
      vi
        .fn()
        .mockResolvedValueOnce(new Response("upstream exploded", { status: 502 }))
        .mockResolvedValueOnce(
          new Response("", { status: 503, statusText: "Service Unavailable" }),
        ),
    );
    await expect(getCredits("u1")).rejects.toThrow("upstream exploded");
    await expect(getCredits("u1")).rejects.toThrow("503 Service Unavailable");
  });

  it("scopes the balance request to the given user", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(
        JSON.stringify({ enabled: true, exempt: false, remaining: 3, next_expiry: null }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    vi.stubGlobal("fetch", fetchMock);
    await expect(getCredits("alpha-friend-a")).resolves.toMatchObject({ remaining: 3 });
    expect(fetchMock).toHaveBeenCalledWith("/api/credits?user=alpha-friend-a", undefined);
  });
});
