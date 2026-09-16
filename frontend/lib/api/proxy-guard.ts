/** Protection for the one public entry point this app has.
 *
 * /api/backend is deliberately reachable without credentials: the browser has
 * none to send, and the API key must never leave the server. That makes it the
 * cheapest way to spend the backend's model time, so the route is fenced on
 * four axes instead — where the request came from, how often, how large, and
 * how many at once. None of this is authentication; it is there so one visitor,
 * one script, or another site cannot exhaust the API behind it.
 *
 * Everything here is pure and synchronous so it can be unit tested; the route
 * handler owns the state.
 */

/** What one call to a route costs against a caller's budget. Scoring a grid is
 * roughly a hundred times the work of scoring a point, so it is priced apart. */
export const ROUTE_COST: Readonly<Record<string, number>> = {
  "prospectivity/heatmap": 10,
  "predict/point": 1,
};
export const DEFAULT_COST = 10;

/** Tokens per caller and how fast they come back. Sized from what the Explorer
 * actually does - a mask switch costs one heatmap, and people switch masks
 * repeatedly - so a session is never throttled, while a script gets about a
 * dozen grids up front and one every five seconds after that. */
export const BUCKET_CAPACITY = 120;
export const REFILL_PER_SECOND = 2;

/** Bodies are {lat, lon}; anything larger is not a request this app makes. */
export const MAX_BODY_BYTES = 4 * 1024;

/** Upstream calls in flight through this process. */
export const MAX_IN_FLIGHT = 8;

/** Callers tracked at once. Bounded, or the limiter becomes the memory leak. */
export const MAX_TRACKED_CLIENTS = 5_000;

export interface Bucket {
  tokens: number;
  updatedAt: number;
}

export interface RateDecision {
  allowed: boolean;
  /** Seconds until the caller could afford this request, for Retry-After. */
  retryAfter: number;
}

/** Token bucket, evaluated at `now` (ms). Mutates `buckets` for this client. */
export function spend(
  buckets: Map<string, Bucket>,
  client: string,
  cost: number,
  now: number,
): RateDecision {
  const bucket = buckets.get(client) ?? { tokens: BUCKET_CAPACITY, updatedAt: now };
  const refilled = Math.min(
    BUCKET_CAPACITY,
    bucket.tokens + ((now - bucket.updatedAt) / 1000) * REFILL_PER_SECOND,
  );
  if (refilled < cost) {
    buckets.set(client, { tokens: refilled, updatedAt: now });
    return { allowed: false, retryAfter: Math.ceil((cost - refilled) / REFILL_PER_SECOND) };
  }
  buckets.set(client, { tokens: refilled - cost, updatedAt: now });
  // Drop the coldest callers rather than letting the map grow without end.
  if (buckets.size > MAX_TRACKED_CLIENTS) {
    const oldest = [...buckets.entries()]
      .sort((a, b) => a[1].updatedAt - b[1].updatedAt)
      .slice(0, buckets.size - MAX_TRACKED_CLIENTS);
    for (const [key] of oldest) buckets.delete(key);
  }
  return { allowed: true, retryAfter: 0 };
}

/** The caller's identity for rate limiting: the nearest thing to a client that
 * a proxied request carries. Falls back to a single shared bucket, which is
 * strict rather than permissive when nothing identifies the caller. */
export function clientKey(headers: Headers): string {
  const forwarded = headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0]!.trim();
  return headers.get("x-real-ip") ?? "unknown";
}

/** True when the request came from this app's own pages.
 *
 * `Sec-Fetch-Site` is sent by every browser that can run this app, so a page on
 * another origin cannot use this proxy as free API credit. Requests with no
 * Origin and no Sec-Fetch-Site (curl, server-side fetches) are allowed through
 * to the rate limiter: refusing them would break same-origin tooling without
 * stopping anyone, since either header can be forged outside a browser. */
export function isSameSite(headers: Headers, selfOrigin: string): boolean {
  const fetchSite = headers.get("sec-fetch-site");
  if (fetchSite) return fetchSite === "same-origin" || fetchSite === "same-site" || fetchSite === "none";
  const origin = headers.get("origin");
  if (origin) return origin === selfOrigin;
  return true;
}

export function tooLarge(body: string): boolean {
  return new TextEncoder().encode(body).length > MAX_BODY_BYTES;
}

export function costOf(path: string): number {
  return ROUTE_COST[path] ?? DEFAULT_COST;
}
