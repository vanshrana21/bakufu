import { NextResponse, type NextRequest } from "next/server";
import { API_KEY_HEADER, proxyTarget } from "@/lib/api/backend-proxy";
import {
  MAX_IN_FLIGHT,
  clientKey,
  costOf,
  isSameSite,
  spend,
  tooLarge,
  type Bucket,
} from "@/lib/api/proxy-guard";

// Every call is a live model request; nothing here may be cached or prerendered.
export const dynamic = "force-dynamic";

const UPSTREAM = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").trim().replace(/\/+$/, "");

/** Per-process limiter state. A single Next server owns it; behind several
 * instances each holds its own share, which lowers the ceiling per instance
 * rather than removing it. */
const buckets = new Map<string, Bucket>();
let inFlight = 0;

const refuse = (status: number, error_code: string, detail: string, remedy?: string, headers?: HeadersInit) =>
  NextResponse.json({ error_code, detail, ...(remedy ? { remedy } : {}) }, { status, headers });

/** Forwards the browser's allowed API calls, adding the server-only API key.
 *
 * The key never reaches the page, so this route is the app's one unauthenticated
 * door to an expensive backend. It is kept narrow: two routes, same-site callers,
 * a token budget per caller, a body ceiling and a cap on calls in flight.
 * Upstream status and body pass through unchanged, so the client's error parsing
 * sees exactly what the API sent.
 */
async function forward(request: NextRequest, { params }: { params: { path: string[] } }): Promise<Response> {
  if (!UPSTREAM) {
    return refuse(
      503,
      "api_not_configured",
      "NEXT_PUBLIC_API_BASE_URL is not set on the server.",
      "Add it to frontend/.env.local and restart the server.",
    );
  }
  const path = params.path.join("/");
  const target = proxyTarget(UPSTREAM, params.path, request.method, request.nextUrl.search);
  if (target === null) {
    return refuse(404, "not_found", `${request.method} /${path} is not available through this proxy.`);
  }
  if (!isSameSite(request.headers, request.nextUrl.origin)) {
    return refuse(403, "forbidden_origin", "This proxy only serves this application's own pages.");
  }

  const body = request.method === "POST" ? await request.text() : undefined;
  if (body !== undefined && tooLarge(body)) {
    return refuse(413, "payload_too_large", "Request body is larger than this proxy accepts.");
  }

  const decision = spend(buckets, clientKey(request.headers), costOf(path), Date.now());
  if (!decision.allowed) {
    return refuse(
      429,
      "rate_limited",
      "Too many model requests from this client.",
      `Retry in about ${decision.retryAfter}s.`,
      { "Retry-After": String(decision.retryAfter) },
    );
  }
  if (inFlight >= MAX_IN_FLIGHT) {
    return refuse(
      503,
      "proxy_busy",
      `${MAX_IN_FLIGHT} model requests are already in flight through this server.`,
      "Retry shortly.",
      { "Retry-After": "5" },
    );
  }

  const headers = new Headers({ Accept: "application/json" });
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  const key = process.env.BAKUFU_API_KEY;
  if (key) headers.set(API_KEY_HEADER, key);

  inFlight += 1;
  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body,
      cache: "no-store",
      signal: request.signal,
    });
    return new Response(upstream.body, {
      status: upstream.status,
      headers: { "Content-Type": upstream.headers.get("content-type") ?? "application/json", "Cache-Control": "no-store" },
    });
  } catch {
    // The browser gave up (navigation, a newer selection); nobody reads this reply.
    if (request.signal.aborted) return new Response(null, { status: 499 });
    return refuse(
      502,
      "upstream_unreachable",
      `Could not reach the API at ${UPSTREAM}.`,
      "Start it with: cd backend && python scripts/run_api.py",
    );
  } finally {
    inFlight -= 1;
  }
}

export { forward as GET, forward as POST };
