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

/** Whether a reverse proxy in front of this app rewrites the forwarding
 * headers. Off by default: a caller can otherwise set X-Forwarded-For itself
 * and take a fresh budget on every request, which is worse than no per-client
 * accounting at all, because it looks like accounting. */
export const TRUST_FORWARDED_FOR = process.env.PROXY_TRUST_FORWARDED_FOR === "true";

/** The caller's identity for rate limiting.
 *
 * Only headers a trusted proxy set are believed. Without one, every caller
 * shares a single bucket: strict rather than forgeable, with the in-flight cap
 * behind it. Set PROXY_TRUST_FORWARDED_FOR=true only when something upstream
 * strips and rewrites these headers. */
export function clientKey(headers: Headers, trustForwarded: boolean = TRUST_FORWARDED_FOR): string {
  if (!trustForwarded) return "shared";
  const forwarded = headers.get("x-forwarded-for");
  if (forwarded) return forwarded.split(",")[0]!.trim();
  return headers.get("x-real-ip") ?? "shared";
}

/** True when the request carries a browser's proof that it came from this app.
 *
 * Every browser that can run this app sends `Sec-Fetch-Site`, so requiring it -
 * or a matching `Origin` - costs a real visitor nothing and refuses both other
 * sites' pages and clients that send neither. It is not authentication: a
 * non-browser client can forge either header. It is there so this endpoint
 * cannot be used as free API credit by someone else's page, and the rate limit
 * behind it is best-effort DoS control, not access control. */
export function isSameSite(headers: Headers, selfOrigin: string): boolean {
  const fetchSite = headers.get("sec-fetch-site");
  if (fetchSite) return fetchSite === "same-origin" || fetchSite === "same-site";
  const origin = headers.get("origin");
  return origin === selfOrigin;
}

export function tooLarge(body: string): boolean {
  return new TextEncoder().encode(body).length > MAX_BODY_BYTES;
}

export function costOf(path: string): number {
  return ROUTE_COST[path] ?? DEFAULT_COST;
}
