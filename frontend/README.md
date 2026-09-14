# Mineral Intelligence Workbench — Earth Observatory

SIH26009 frontend: Next.js 14, React 18, strict TypeScript/Zod, Tailwind, Radix/shadcn-style primitives, Zustand, Mapbox GL JS and Recharts. All four routes are implemented with clearly labelled demonstration data.

## Run

```sh
cd frontend
npm ci
npm run dev:sih
```

Open http://localhost:3001/explorer. Port 3000 belongs to another local application; the SIH scripts use 3001.

Set the browser-safe Mapbox token in frontend/.env.local as NEXT_PUBLIC_MAPBOX_TOKEN (or NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN). Restart after changes. No token was present in this workspace; no credentials are included.

With a token, Mapbox loads satellite-streets-v12. Without one, a dynamically loaded MapLibre 5.6.2 fallback renders the identical synthetic layer specification and NASA GIBS Blue Marble geographic context. The screen explicitly names the renderer limitation, basemap and synthetic overlay. If imagery fails, local screening geometry and the location list still work. WebGL failure leaves the list/inspector accessible.

## Implemented views
- / — Operational briefing: latest monthly production, next forecast, downside risk and pending-review count; forecast chart, screening register and review register.
- /explorer — Survey panel, Ghost Reserve filter, masks, point selection, scope search, raw/screened evidence and SHAP; live-rendered mock polygon overlay, exclusion hatching and waste diamonds; forecast/risk/constraints column.
- /production — Company-wide forecast, interval, issue date, cutoff, downside event and model limitations.
- /actions — Four demonstration proposals; register filters and evidence selection. /actions?review=demo-action-04 opens the selected rule. No approvals, assignments or operational commands are sent.

## Source of truth
The project-state source is /Users/vanshrana/Downloads/SIH26009_PROJECT_STATE.md, ending at Phase 2.9.2. Operational fixtures and Ghost Reserve inventory are user-requested UI extensions, not reported model results.

lib/contracts.ts remains the proposed normalized frontend API contract. Backend agreement and a normalization adapter are still required. The frontend does not invent an existing backend endpoint or claim its mock schemas are deployed FastAPI responses.

## Integration seams
- lib/api/predictions.ts: prediction adapter, request cancellation and response validation.
- fixtures/predictions.ts: shared Ghost predicate and scope-first mock response.
- fixtures/prospectivity-surface.ts: synthetic display polygons. These are neither actual dump footprints nor a metric 5km buffer nor a validated belt boundary.
- public/styles/prospectivity.layers.json: committed fill style for prediction-cells. lib/map/prospectivity-layers.ts removes source-layer for GeoJSON and preserves it for vector tiles.
- lib/map/register-mask-pattern.ts: shared power-of-two exclusion sprite.
- fixtures/operations.ts: typed history/forecast/risk/actions, four review records and derived vital signs. Owner/priority/date display metadata is separate from strict ActionResponse.
- components/motion/: Reveal, Odometer and SpecimenDrift. Dependency-free (IntersectionObserver + CSS); motion is gated on a `.motion-ready` class so no-JS, print and reduced-motion always render complete evidence.
- components/operations/review-register.tsx: filtering and selection. Future review persistence must use a backend audit trail.

## Rules that must survive backend integration
- Keep raw_score, final_score, mask_applied and scope_status unchanged. Out-of-scope/unknown scores are null; excluded scores are zero policy outcomes.
- Ghost eligibility is waste/slag AND inside the occurrence-buffer union AND in geographic scope, independent of mask toggles.
- Real scope and metric-distance membership must come from the backend. Sandur/Bonai fixtures are not a production geofence or a general geocoder.
- Geological source remains a coarse Macrostrat 1:5M proxy, not GSI 1:50K.
- Numeric inspector values come from the response, never from sampled map colors. SHAP explains its declared classifier output before PU adjustment/masks.
- A slag heap in Sausar is not validated for recoverability. No ore quantity, assay result or environmental clearance is inferred.
- Production and risk are company-wide. Risk is relative to an issued forecast, not a buyer demand target. Intervals and calibration remain explicitly unvalidated.
- All four action records are proposed, with reviewer/date null. No invented approvals or operational mutations.
- The original rainfall-deficit → pump-increase example still requires causal/domain review; the demo uses separate explicitly unvalidated rules.

## Validation

Run serially with other Next dev servers stopped; build and dev share .next.

```sh
npm run typecheck
npm test
PLAYWRIGHT_CHANNEL=chrome npm run test:e2e
NEXT_TELEMETRY_DISABLED=1 npm run build
```

15 unit tests cover existing contracts, mock map score consistency, Ghost filtering, GeoJSON/vector style adaptation and review counts. Browser specs retain the scope/mask/SHAP/rapid-selection/forecast-horizon checks, and add actual rendered feature counts, review selection, status filters and direct review links. Screenshots cover presentation, smaller desktop, mobile and print.

Live authenticated Mapbox imagery and the absent backend services are not claimed as integration-tested. NASA access is optional geographic context, not a deterministic test dependency.

## Design and references
Current direction is Earth Observatory (precision industrial), taking its material
character and motion restraint from https://sstr.tech. See DESIGN.md for the identity,
type scale and the three-effect motion policy; docs/DESIGN_RESEARCH.md is archived
research from the earlier graphite/oxide study.
- NASA layer: [GIBS WMTS capabilities](https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml), BlueMarble_ShadedRelief_Bathymetry / GoogleMapsCompatible_Level8.
- [Mapbox fill layers](https://docs.mapbox.com/style-spec/reference/layers/#fill)
- [MapLibre documentation](https://maplibre.org/maplibre-gl-js/docs/)

## Dependency boundary
Next.js 14.2.35 is retained to honor the requested major version. Its existing upstream security advisory requires a separately planned major-version upgrade before public production deployment. No unrelated major migration was made for this design change.
