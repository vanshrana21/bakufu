import { describe, expect, it } from "vitest";
import {
  BUCKET_CAPACITY,
  MAX_BODY_BYTES,
  MAX_TRACKED_CLIENTS,
  REFILL_PER_SECOND,
  clientKey,
  costOf,
  isSameSite,
  spend,
  tooLarge,
  type Bucket,
} from "@/lib/api/proxy-guard";

/** /api/backend is this app's only unauthenticated door to an expensive API.
 * These are the limits that keep one caller from spending all of it. */
describe("proxy abuse controls", () => {
  it("prices a heatmap far above a point prediction", () => {
    expect(costOf("prospectivity/heatmap")).toBeGreaterThan(costOf("predict/point") * 5);
    // An unknown route is charged the expensive rate, not the cheap one.
    expect(costOf("something/new")).toEqual(costOf("prospectivity/heatmap"));
  });

  it("lets a normal session through and then refuses a flood", () => {
    const buckets = new Map<string, Bucket>();
    const now = 1_000_000;
    // The Explorer's own pattern: a heatmap and a handful of point queries.
    expect(spend(buckets, "visitor", costOf("prospectivity/heatmap"), now).allowed).toBe(true);
    for (let i = 0; i < 10; i += 1) {
      expect(spend(buckets, "visitor", costOf("predict/point"), now).allowed).toBe(true);
    }

    const refusals: number[] = [];
    for (let i = 0; i < 50; i += 1) {
      const decision = spend(buckets, "flooder", costOf("prospectivity/heatmap"), now);
      if (!decision.allowed) refusals.push(decision.retryAfter);
    }
    expect(refusals.length).toBeGreaterThan(30);
    expect(refusals[0]).toBeGreaterThan(0);
  });

  it("refills over time rather than locking a caller out for good", () => {
    const buckets = new Map<string, Bucket>();
    const start = 5_000_000;
    while (spend(buckets, "visitor", costOf("prospectivity/heatmap"), start).allowed) {
      /* drain */
    }
    const waited = start + (BUCKET_CAPACITY / REFILL_PER_SECOND) * 1000;
    expect(spend(buckets, "visitor", costOf("prospectivity/heatmap"), waited).allowed).toBe(true);
  });

  it("keeps one caller's budget separate from another's", () => {
    const buckets = new Map<string, Bucket>();
    const now = 2_000_000;
    while (spend(buckets, "noisy", costOf("prospectivity/heatmap"), now).allowed) {
      /* drain */
    }
    expect(spend(buckets, "quiet", costOf("prospectivity/heatmap"), now).allowed).toBe(true);
  });

  it("does not grow its client table without bound", () => {
    const buckets = new Map<string, Bucket>();
    for (let i = 0; i < MAX_TRACKED_CLIENTS + 500; i += 1) {
      spend(buckets, `client-${i}`, 1, 3_000_000 + i);
    }
    expect(buckets.size).toBeLessThanOrEqual(MAX_TRACKED_CLIENTS);
  });

  it("identifies the caller behind a proxy header", () => {
    expect(clientKey(new Headers({ "x-forwarded-for": "203.0.113.7, 10.0.0.1" }))).toBe("203.0.113.7");
    expect(clientKey(new Headers({ "x-real-ip": "198.51.100.4" }))).toBe("198.51.100.4");
    // Nothing identifies it: one shared bucket, which is the strict choice.
    expect(clientKey(new Headers())).toBe("unknown");
  });

  it("serves this app's pages and refuses another site's", () => {
    const self = "http://localhost:3000";
    expect(isSameSite(new Headers({ "sec-fetch-site": "same-origin" }), self)).toBe(true);
    expect(isSameSite(new Headers({ "sec-fetch-site": "none" }), self)).toBe(true);
    expect(isSameSite(new Headers({ "sec-fetch-site": "cross-site" }), self)).toBe(false);
    expect(isSameSite(new Headers({ origin: "https://someone-else.example" }), self)).toBe(false);
    expect(isSameSite(new Headers({ origin: self }), self)).toBe(true);
  });

  it("refuses a body larger than the requests this app makes", () => {
    expect(tooLarge(JSON.stringify({ lat: 21.7, lon: 79.8 }))).toBe(false);
    expect(tooLarge("x".repeat(MAX_BODY_BYTES + 1))).toBe(true);
    // Multi-byte characters count as bytes, not characters.
    expect(tooLarge("é".repeat(MAX_BODY_BYTES / 2 + 1))).toBe(true);
  });
});
