/** Shared rules for reaching the FastAPI backend from the browser.
 *
 * Server Components call the API directly. The browser never does: it calls
 * this app's /api/backend route, which forwards to the API and adds the API key
 * on the server, so the key is never shipped to the page. Only the routes the
 * browser actually uses are forwarded; anything else is a 404 rather than an
 * open proxy to the whole API.
 *
 * The allowlist is not written here — it is derived from lib/api/routes.ts,
 * where every route this app calls is declared with the surface it belongs to.
 * That is what stops the two from drifting: a loader that moves into a client
 * component fails tests/unit/browser-surface.test.ts until its route is marked
 * `browser`, and a route marked `browser` is forwarded automatically.
 */

import { BROWSER_ROUTES } from "./routes";

export const BROWSER_PROXY_PREFIX = "/api/backend";
export const API_KEY_HEADER = "X-API-Key";

export { BROWSER_ROUTES };

/** The upstream URL for a proxied request, or null when it is not allowed.
 *
 * Exact match on the joined path and the method. `Object.hasOwn` rather than
 * `in`, so `constructor` and `toString` are not paths; and the segments are
 * checked for traversal before they are joined, so no `..` can walk the proxy
 * onto a path the allowlist never named.
 */
export function proxyTarget(
  upstreamBase: string,
  segments: readonly string[],
  method: string,
  search: string,
): string | null {
  // A segment containing a slash, a dot-dot, or an encoded one would be joined
  // into a path that no longer equals the one the allowlist matched.
  if (segments.some((segment) => segment === "." || segment === ".." || /[/\\]/.test(segment) || segment.includes("%"))) {
    return null;
  }
  const path = segments.join("/");
  if (!Object.hasOwn(BROWSER_ROUTES, path) || BROWSER_ROUTES[path] !== method) return null;
  return `${upstreamBase}/${path}${search}`;
}
