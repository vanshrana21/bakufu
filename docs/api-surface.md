# Which API routes the browser may reach

This is the security boundary of the whole application, so it is written down
once and checked by tests rather than argued about in review.

## The rule

The FastAPI backend requires `X-API-Key` on **every** route, including `GET /`.
That key must never reach the browser, so:

- **Server Components** call the API directly, adding `BAKUFU_API_KEY` on the
  server. Nothing about this is reachable from a page.
- **Client components** call this app's own `/api/backend/...` route, which adds
  the key server-side and forwards the request.

`/api/backend` is therefore the one unauthenticated door to an expensive API. It
forwards exactly the routes a browser actually calls, and answers `404` to every
other path and method.

## The three surfaces

| Route | Method | Surface | Why |
|---|---|---|---|
| `/prospectivity/heatmap` | GET | **browser-proxied** | `use-prospectivity-surface` refetches on every mask change |
| `/predict/point` | POST | **browser-proxied** | `use-prediction` scores the selected site |
| `/dashboard/summary` | GET | server-only | awaited in `app/(workspace)/operations/page.tsx` |
| `/forecast` | GET | server-only | operations and production pages |
| `/production/history` | GET | server-only | chart series and the last observed month |
| `/shortfall/risk` | GET | server-only | allowed to fail independently of the forecast |
| `/recommendations` | GET | server-only | the review register |
| `/recommendations/scenario/{month}` | GET | server-only | exported for the replay demo; no current caller |
| everything else | — | **not exposed** | `/train`, `/predict/bbox`, `/boreholes`, `/priors`, `/foreign`, `/mines`, `/masks`, `/forecast/retrain`, … |

"Server-only" does not mean secret — those responses are rendered into the page.
It means the *request* is made by the Next.js server, so the route does not need
to be reachable from an anonymous caller, and is not.

## Why the proxy is not simply opened up

Adding the server-only routes to the allowlist has been proposed more than once,
on the reasoning that the frontend "calls" them. It does — from the server. The
browser never does, and the tests below prove it. Forwarding them anyway would
put `/forecast`, `/shortfall/risk` and `/recommendations` — the SHAP path, which
is the most expensive thing the API computes — behind an endpoint with no
credentials, for no functional gain.

If a loader ever does move into a client component, the fix is one line in
`frontend/lib/api/routes.ts` (`surface: "server"` → `"browser"`), and the tests
will refuse to pass until it is made.

## How this is enforced

Nothing here relies on someone remembering it.

**`frontend/lib/api/routes.ts`** declares every route the app calls, with its
method, its query parameters and its surface. The proxy allowlist is *derived*
from it, so the two cannot disagree.

**`tests/unit/browser-surface.test.ts`** walks the real import graph from every
`"use client"` file — skipping `import type`, which is erased before a bundle
exists — and asserts that the set of API paths reachable in a browser is exactly
the proxied set. Both directions fail: a route the browser can reach but the
proxy refuses (a 404 in the product), and a route proxied but unreachable
(surface for nothing). It also asserts `lib/api/load.ts`, `dashboard.ts`,
`forecast.ts` and `shortfall.ts` are not in the client graph at all.

**`tests/unit/route-registry.test.ts`** checks every declared route against
`lib/api/backend-routes.json` — generated from the live OpenAPI document by
`backend/scripts/export_routes.py` — for path, method and query-parameter names,
and asserts the proxy refuses every route the app does not call.

**`backend/tests/test_route_manifest.py`** fails when that manifest is stale.
Regenerate it with:

```bash
cd backend && python scripts/export_routes.py
```

**`backend/tests/test_security.py`** enumerates every operation in the OpenAPI
document and asserts each answers `401` without a key and with a wrong key, so a
router added later is covered the day it is added rather than the day someone
remembers to list it.

## What the proxy is, and is not

It is not authentication. It enforces:

- an exact path+method allowlist, with traversal-shaped segments refused before
  the lookup;
- a same-site check (`Sec-Fetch-Site`, or a matching `Origin`) — a browser
  signal, forgeable by a non-browser client;
- a token bucket per caller, an in-flight cap, and a 4 KB body ceiling;
- `no-store` on everything, because model output changes when an artifact is
  promoted.

A caller can forge `X-Forwarded-For`, so those headers are ignored unless
`PROXY_TRUST_FORWARDED_FOR=true` says a reverse proxy rewrites them; without
one, every caller shares a single bucket — strict rather than forgeable. The
limiter is per-process, so several Next instances each hold their own share.

Missing configuration fails loudly rather than silently: no
`NEXT_PUBLIC_API_BASE_URL` is `503 api_not_configured`, and no `BAKUFU_API_KEY`
is `503 api_key_not_configured` rather than an anonymous request that comes back
`401` looking like a broken backend.
