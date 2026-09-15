/** Shared rules for reaching the FastAPI backend from the browser.
 *
 * Server Components call the API directly. The browser never does: it calls
 * this app's /api/backend route, which forwards to the API and adds the API key
 * on the server, so the key is never shipped to the page. Only the routes the
 * browser actually uses are forwarded; anything else is a 404 rather than an
 * open proxy to the whole API.
 */

export const BROWSER_PROXY_PREFIX = "/api/backend";
export const API_KEY_HEADER = "X-API-Key";

/** API path (without a leading slash) -> the one method the browser may use. */
export const BROWSER_ROUTES: Readonly<Record<string, "GET" | "POST">> = {
  "prospectivity/heatmap": "GET",
  "predict/point": "POST",
};

/** The upstream URL for a proxied request, or null when it is not allowed. */
export function proxyTarget(upstreamBase: string, segments: readonly string[], method: string, search: string): string | null {
  const path = segments.join("/");
  if (!Object.hasOwn(BROWSER_ROUTES, path) || BROWSER_ROUTES[path] !== method) return null;
  return `${upstreamBase}/${path}${search}`;
}
