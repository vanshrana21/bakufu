import { NextResponse, type NextRequest } from "next/server";
import { API_KEY_HEADER, proxyTarget } from "@/lib/api/backend-proxy";

// Every call is a live model request; nothing here may be cached or prerendered.
export const dynamic = "force-dynamic";

const UPSTREAM = (process.env.NEXT_PUBLIC_API_BASE_URL ?? "").trim().replace(/\/+$/, "");

/** Forwards the browser's allowed API calls, adding the server-only API key.
 * Upstream status and body pass through unchanged, so the client's error
 * parsing sees exactly what the API sent. */
async function forward(request: NextRequest, { params }: { params: { path: string[] } }): Promise<Response> {
  if (!UPSTREAM) {
    return NextResponse.json(
      { error_code: "api_not_configured", detail: "NEXT_PUBLIC_API_BASE_URL is not set on the server.", remedy: "Add it to frontend/.env.local and restart the server." },
      { status: 503 },
    );
  }
  const target = proxyTarget(UPSTREAM, params.path, request.method, request.nextUrl.search);
  if (target === null) {
    return NextResponse.json(
      { error_code: "not_found", detail: `${request.method} /${params.path.join("/")} is not available through this proxy.` },
      { status: 404 },
    );
  }

  const headers = new Headers({ Accept: "application/json" });
  const contentType = request.headers.get("content-type");
  if (contentType) headers.set("Content-Type", contentType);
  const key = process.env.BAKUFU_API_KEY;
  if (key) headers.set(API_KEY_HEADER, key);

  try {
    const upstream = await fetch(target, {
      method: request.method,
      headers,
      body: request.method === "POST" ? await request.text() : undefined,
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
    return NextResponse.json(
      { error_code: "upstream_unreachable", detail: `Could not reach the API at ${UPSTREAM}.`, remedy: "Start it with: cd backend && python scripts/run_api.py" },
      { status: 502 },
    );
  }
}

export { forward as GET, forward as POST };
