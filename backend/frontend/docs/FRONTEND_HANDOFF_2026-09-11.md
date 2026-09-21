# Frontend Handoff — SIH26009 Mineral Intelligence Workbench

**Audit date:** 2026-09-11 · **Auditor:** read-only, no code modified
**Repo:** `/Users/vanshrana/Desktop/sih/frontend` (untracked — `git status` shows `?? frontend/`)
**Stack:** Next.js 14.2.35 App Router · React 18.3.1 · TypeScript 5.7.3 strict · Tailwind 3.4.17 · Zod 3.24.2 · Zustand 5.0.3 · Mapbox GL 3.10.0 + MapLibre GL 5.6.2 · Recharts 3.10.1

**Strategy context:** integration-first. Everything below is tagged `[FUNCTIONAL]` (required to wire a live backend) or `[DECORATIVE]` (safe to disable during the simple-UI phase).

> **Read §10.1 before anything else.** The Command Center is currently unreachable in the browser due to a route collision. Four of the six Playwright specs fail because of it.

---

## 1. ROUTE & FILE MAP

### 1.1 `app/` — complete

```
app/
├── layout.tsx                        11 lines · root <html>/<body>, imports 4 CSS files
├── globals.css                      321 lines · all design tokens + component CSS
├── icon.svg                           1 line  · favicon — STALE Survey-Edition maroon
├── page.tsx                           5 lines · renders <HeroSection/> — COLLIDES, see §10.1
└── (workspace)/                              · route group, does NOT affect URL paths
    ├── layout.tsx                    11 lines · <ExplorerProvider><AppShell>, imports operations.css
    ├── error.tsx                      5 lines · route-segment error boundary
    ├── page.tsx                      65 lines · Command Center  → "/"  (SHADOWED)
    ├── explorer/page.tsx              7 lines · Explorer        → "/explorer"
    ├── production/page.tsx           41 lines · Production&Risk → "/production"
    └── actions/page.tsx              11 lines · Corrective Act. → "/actions"
```

### 1.2 `components/` — complete (38 files)

```
components/
├── hero-section.tsx                        [DECORATIVE] GSAP scroll hero, renders at "/"
├── shell/
│   ├── app-shell.tsx                       [FUNCTIONAL] masthead + nav + scope strip
│   └── mineral-specimen.tsx                [DECORATIVE] broken <img>, see §10.3
├── explorer/
│   ├── explorer-provider.tsx               [FUNCTIONAL] Zustand context provider
│   ├── explorer-workspace.tsx              [FUNCTIONAL] Explorer shell + GhostReserveToggle + MaskToggleGroup
│   ├── map-canvas.tsx                      [FUNCTIONAL] Mapbox renderer + tokenless fallback switch
│   ├── tokenless-map-canvas.tsx            [FUNCTIONAL] MapLibre renderer (no-token path)
│   ├── map-legend.tsx                      [FUNCTIONAL] colour ramp + hatch legend
│   ├── site-inspector.tsx                  [FUNCTIONAL] raw/screened scores, masks, SHAP tabs
│   ├── shap-bar-chart.tsx                  [FUNCTIONAL] SHAP contribution bars
│   └── map-presentation.css       153 lines [FUNCTIONAL] map chrome styling
├── operations/
│   ├── vital-signs.tsx                     [FUNCTIONAL] 4 KPI tiles
│   ├── forecast-risk-panel.tsx             [FUNCTIONAL] forecast + risk composite
│   ├── production-chart.tsx                [FUNCTIONAL] Recharts actual/forecast/interval
│   ├── risk-gauge.tsx                      [FUNCTIONAL] donut + severity bands
│   ├── review-register.tsx                 [FUNCTIONAL] proposed-actions table
│   ├── action-evidence.tsx                 [FUNCTIONAL] trigger clauses + evidence
│   ├── actions-workbench.tsx               [FUNCTIONAL] register + evidence pane
│   ├── survey-outlook.tsx                  [FUNCTIONAL] SurveyOutlook + KeyConstraints
│   ├── print-briefing.tsx                  [FUNCTIONAL] print button, opens <details> first
│   └── operations.css             116 lines [FUNCTIONAL]
├── motion/                                 (13 files — 11 ORPHANED, see §10.6)
│   ├── text-reveal.tsx                     [DECORATIVE] imported by forecast-risk-panel
│   ├── eyebrow-bracket.tsx                 [DECORATIVE] imported by forecast-risk-panel
│   ├── odometer.tsx  reveal.tsx  specimen-drift.tsx            ORPHANED (0 importers)
│   ├── preloader.tsx  page-transition.tsx  magnetic-button.tsx ORPHANED
│   ├── nav-link.tsx  plus-pattern.tsx  line-plus-divider.tsx   ORPHANED
│   └── text-fill.tsx  theme-section.tsx                        ORPHANED
└── ui/
    ├── button.tsx                          [FUNCTIONAL] 5 importers
    ├── switch.tsx                          [FUNCTIONAL] mask + ghost toggles
    └── tabs.tsx                            [FUNCTIONAL] inspector + forecast panel
```

### 1.3 Supporting trees

```
lib/
├── contracts.ts              181 lines  [FUNCTIONAL] 16 importers — the schema spine
├── utils.ts                             [FUNCTIONAL] cn()
├── api/predictions.ts         26 lines  [FUNCTIONAL] the ONLY adapter; fixture-backed
├── map/prospectivity-layers.ts          [FUNCTIONAL] strips source-layer for GeoJSON mode
├── map/register-mask-pattern.ts         [FUNCTIONAL] 8×8 exclusion hatch sprite
└── animations/                          ORPHANED (0 importers)
    ├── gsap-register.ts   text-split.ts   smooth-scroll.tsx (lenis)
stores/explorer-store.ts        21 lines  [FUNCTIONAL] Zustand vanilla store
hooks/use-prediction.ts         28 lines  [FUNCTIONAL] adapter + race-cancellation
fixtures/
├── predictions.ts             97 lines  [FUNCTIONAL]
├── operations.ts              83 lines  [FUNCTIONAL]
└── prospectivity-surface.ts   36 lines  [FUNCTIONAL]
tests/unit/{contracts,prospectivity-surface}.test.ts
tests/e2e/{briefing,explorer,interaction-regression}.spec.ts
public/{styles/prospectivity.layers.json, test-img-1.jpg, test-img-2.jpg,
        hero-mining-1.jpg, hero-mining-2.jpg, hero-video.mp4, hero-scroll.mp4,
        images/manganese-specimen-original.png}
docs/DESIGN_RESEARCH.md  (35 KB, archived graphite/oxide-era research)
```

### 1.4 The four views

| View | Nav href | Renders from | Root component | Status |
|---|---|---|---|---|
| **Command Center** | `/` | [app/(workspace)/page.tsx](app/(workspace)/page.tsx) | inline JSX | **UNREACHABLE** — shadowed by [app/page.tsx:1](app/page.tsx#L1) |
| **Explorer** | `/explorer` | [app/(workspace)/explorer/page.tsx:6](app/(workspace)/explorer/page.tsx#L6) | `<ExplorerWorkspace/>` | working |
| **Production & Risk** | `/production` | [app/(workspace)/production/page.tsx:8](app/(workspace)/production/page.tsx#L8) | inline JSX | working |
| **Corrective Actions** | `/actions` | [app/(workspace)/actions/page.tsx:4](app/(workspace)/actions/page.tsx#L4) | `<ActionsWorkbench/>` | working |

Nav is defined in [components/shell/app-shell.tsx:8-13](components/shell/app-shell.tsx#L8). Clicking "Command Center" navigates to `/`, which serves the hero — not the dashboard.

---

## 2. DESIGN SYSTEM STATE

### 2.1 The Sausar Survey theme is GONE

The maroon/cream editorial theme was replaced. Current theme is **"Earth Observatory — precision industrial"**, declared at [app/globals.css:5-7](app/globals.css#L5).

| | Sausar Survey (old) | Earth Observatory (current) |
|---|---|---|
| Background | `#F1EDE5` cream | `#EFF0F1` cool grey |
| Brand | `#662638` burgundy | `#C44016` mineral orange |
| Accent | — | `#FE5B2A` brand-orange |
| Secondary | — | `#236D64` oxide teal |
| Type | Georgia serif | Noto Sans Variable |
| Character | editorial/print | instrument panel, 1px borders |

### 2.2 Active token set — `app/globals.css` `:root` (lines 8-86)

**Neutral ramp** (SSTR-reference discipline): `--grey-900 #0C0C0C`, `--grey-850 #141415`, `--grey-800 #18191B`, `--grey-750 #222326`, `--grey-700 #2F3032`, `--grey-600 #464749`, `--grey-500 #747576`, `--grey-400 #8B8C8D`, `--grey-300 #A3A3A4`, `--grey-200 #C3C4C8`, `--grey-150 #E0E1E3`, `--grey-100 #EFF0F1`

**Surface:** `--background #EFF0F1` · `--foreground #20272B` · `--surface #FAFBFB` · `--surface-raised #E8EAEB` · `--sidebar #E0E1E3` · `--card #FAFBFB` · `--popover #FFFFFF` · `--canvas #18191B` · `--canvas-ink #EFF0F1` · `--canvas-muted #A3A3A4`

**Brand:** `--primary #C44016` · `--primary-hover #A73210` · `--primary-soft #FBECE6` · `--brand-orange #FE5B2A` · `--brand-orange-400 #FE7C55` · `--brand-orange-600 #E75326` · `--ring #C44016`

**Semantic (deliberately independent of brand):** `--oxide #236D64` / `--oxide-soft #E6F0ED` · `--success #226146` / `#E5F0E9` · `--warning #80520D` / `#FBF3DF` · `--critical #AE323D` / `#F9E9EB` · `--info #245C78` / `#E5F0F5` · `--destructive #AE323D` · `--metadata #58636B` · `--muted #E9EEEF` / `--muted-foreground #526069` · `--border #C3C4C8` · `--border-dark #2F3032` · `--input #8B8C8D`

**Map ramp** (mirrors `public/styles/prospectivity.layers.json`): `--map-low #ADAEA2` · `--map-quarter #E0C396` · `--map-mid #F2B153` · `--map-three-quarter #F48137` · `--map-high #E45227` · `--map-ghost #62C5B5` · `--map-excluded #B9C4CC` · `--map-selection #FFFFFF` · `--map-out-of-scope #697680`

**Chart:** `--chart-actual #33494D` · `--chart-forecast #C44016` · `--chart-interval #F4DCD0` · `--chart-positive #236D64` · `--chart-negative #C44016`

**Scale/motion:** `--space-1..12` (4/8/12/16/24/32/48px) · `--radius 0.25rem` · z-index scale `--z-map 0 … --z-toast 50` · `--ease-out cubic-bezier(.22,.61,.36,1)` · `--dur-fast 180ms` · `--dur-reveal 420ms`

**Typography classes:** `.label/.section-label/…` = 10px, 500, `.1em` tracking, uppercase ([globals.css:88-91](app/globals.css#L88)). `.display-figure/…` = weight 400, `-.035em`, line-height 1, tabular-nums ([globals.css:92-95](app/globals.css#L92)).

`tailwind.config.ts` maps every colour to a `var(--token)` — no hardcoded palette in Tailwind. Custom spacing: `rail 224px`, `inspector 368px`. Radii capped at 8px.

### 2.3 Visual changes since Sausar Survey

1. Full token replacement — maroon/cream → charcoal/orange/teal (above).
2. Serif → `Noto Sans Variable` throughout (`@fontsource-variable/noto-sans`).
3. Masthead restyled to `.observatory-masthead` — dark `--canvas` bar, 82px, orange brand square ([globals.css:112-120](app/globals.css#L112)).
4. `.scope-strip` added — monospace sub-bar under masthead ([globals.css:121-123](app/globals.css#L121)).
5. Display headings now uppercase, weight 400, `clamp(30px,3.1vw,46px)` ([globals.css:126-129](app/globals.css#L126)).
6. `components/explorer/map-presentation.css` added (153 lines) — map chrome, legend, token notice.
7. GSAP + Lenis + Splitting added as dependencies; 13-file `components/motion/` + 3-file `lib/animations/` built. Only 2 wired.
8. `components/hero-section.tsx` added — full-bleed GSAP scroll-pinned image crossfade at `/`.
9. Print stylesheet retained and extended ([globals.css:297-321](app/globals.css#L297)) — A4 landscape, greyscale SVG, map hidden.

### 2.4 Stale-theme remnants (visible bugs)

| File | Line | Value | Issue |
|---|---|---|---|
| [app/icon.svg](app/icon.svg) | 1 | `#662638` + `#fff9f1` | favicon still Survey-Edition maroon/cream |
| [components/hero-section.tsx](components/hero-section.tsx) | 109, 111, 136 | `#874B2D` ×3 | old oxide-brown, not `--brand-orange` |

---

## 3. COMPONENT INVENTORY (per view)

### 3.1 Shell (all views)

| Component | Data consumed | Tag |
|---|---|---|
| `AppShell` | `usePathname()` only | **[FUNCTIONAL]** |
| `ExplorerProvider` | none (creates store) | **[FUNCTIONAL]** |
| `WorkspaceError` | Next error boundary | **[FUNCTIONAL]** |

### 3.2 Command Center — `app/(workspace)/page.tsx`

| Component | Data consumed | Tag |
|---|---|---|
| `VitalSigns` | `vitalSignsFixture` | **[FUNCTIONAL]** → `/dashboard/summary` |
| `ForecastRiskPanel` | props `forecastFixture`, `riskFixture`, `historyFixture` | **[FUNCTIONAL]** → `/forecast` + `/shortfall/risk` |
| `ReviewRegister` | `reviewRegisterFixture` | **[FUNCTIONAL]** → `/recommendations` |
| `ActionEvidence` | prop `actionFixture` | **[FUNCTIONAL]** |
| `PrintBriefing` | DOM only | [DECORATIVE] |
| `MineralSpecimen` | static `<img>` | **[DECORATIVE]** — broken, §10.3 |
| inline screening register table | `DEMO_SITES` + `isGhostReserveCandidate` | **[FUNCTIONAL]** |
| `.observatory-hero` header block | static copy | [DECORATIVE] |

### 3.3 Explorer — `/explorer`

| Component | Data consumed | Tag |
|---|---|---|
| `ExplorerWorkspace` | store (`ghostOnly`,`activeMask`,`selectedSiteId`), `DEMO_SITES` | **[FUNCTIONAL]** |
| `GhostReserveToggle` | store `ghostOnly`/`setGhostOnly` | **[FUNCTIONAL]** |
| `MaskToggleGroup` | store `activeMask`/`setMask` | **[FUNCTIONAL]** |
| `MapCanvas` | props `sites`,`activeMask`,`selectedSiteId`; `buildProspectivitySurface` | **[FUNCTIONAL]** → `/prospectivity/heatmap` |
| `TokenlessMapCanvas` | same props, MapLibre | **[FUNCTIONAL]** fallback |
| `MapLegend` | hardcoded `screeningColors` | **[FUNCTIONAL]** (legend must match live ramp) |
| `SiteInspector` | `usePrediction()` → `PredictionResponse` | **[FUNCTIONAL]** → `POST /predict/point` |
| `ShapBarChart` | `prediction.shap` | **[FUNCTIONAL]** |
| `MaskExplanationPanel` | `prediction.mask_results` | **[FUNCTIONAL]** → `/masks` |
| `SurveyOutlook` | `forecastFixture`,`historyFixture`,`riskFixture` (imports directly) | [DECORATIVE] on this view |
| `ReviewRegister` (repeat) | `reviewRegisterFixture` | [DECORATIVE] on this view |

### 3.4 Production & Risk — `/production`

| Component | Data consumed | Tag |
|---|---|---|
| `ForecastRiskPanel` | props | **[FUNCTIONAL]** |
| ↳ `ProductionChart` | `ForecastResponse` + `historyFixture` | **[FUNCTIONAL]** |
| ↳ `RiskGauge` | `RiskResponse` | **[FUNCTIONAL]** |
| `KeyConstraints` | hardcoded 4 labels | [DECORATIVE] |
| `ReviewRegister` | `reviewRegisterFixture` | **[FUNCTIONAL]** |
| `PrintBriefing` | DOM | [DECORATIVE] |
| `.instrument-rail` forecast-basis block | **hardcoded strings** ("September 2026", "1 September 2026 · UTC") | [DECORATIVE] — §10.8 |
| `.forecast-reading` explainer grid | static copy | [DECORATIVE] |

### 3.5 Corrective Actions — `/actions`

| Component | Data consumed | Tag |
|---|---|---|
| `ActionsWorkbench` | `reviewRegisterFixture`, `searchParams.review` | **[FUNCTIONAL]** |
| ↳ `ReviewRegister` (`selectedId`/`onSelect`) | same | **[FUNCTIONAL]** |
| ↳ `ActionEvidence` | selected `ActionResponse` | **[FUNCTIONAL]** |
| `PrintBriefing` | DOM | [DECORATIVE] |

### 3.6 Orphans — zero importers, zero render paths

`components/motion/`: `odometer`, `reveal`, `specimen-drift`, `preloader`, `page-transition`, `magnetic-button`, `nav-link`, `plus-pattern`, `line-plus-divider`, `text-fill`, `theme-section`
`lib/animations/`: `gsap-register.ts`, `text-split.ts`, `smooth-scroll.tsx`

All **[DECORATIVE]**, all deletable without touching a render path.

---

## 4. DATA LAYER

### 4.1 `lib/contracts.ts` — every schema

Header comment ([contracts.ts:3-6](lib/contracts.ts#L3)) is explicit: *"Proposed frontend v1 contract, NOT a claim about the current FastAPI wire schema… Adapt actual backend responses at lib/api; never silently fabricate fields."*

**Primitives (internal, not exported):** `Nonempty` = trimmed min(1) · `Finite` = `z.number().finite()` · `Fraction` = 0..1 · `ProspectivityScore` = 0..**0.99** (documented v6 cap) · `Timestamp` = `z.string().datetime({offset:true})` — **requires ISO-8601 with explicit offset**.

| Export | Kind | Strictness | Fields |
|---|---|---|---|
| `MonthSchema` | string regex | n/a | `^\d{4}-(0[1-9]\|1[0-2])$` |
| `MaskModeSchema` | enum | n/a | `none` `geological` `occurrence_buffer` `both` |
| `ScopeStatusSchema` | enum | n/a | `in_scope` `out_of_scope` `unknown` |
| `ProvenanceSchema` | object | **default (strips unknown)** | `data_origin:"fixture"\|"live"`, `source`, `model_version`, `generated_at` |
| `LocationSchema` | object | default | `longitude` (-180..180), `latitude` (-90..90) |
| `AssetSchema` | object | default | `id`, `name`, `asset_type:"historical_waste_dump"\|"slag_heap"\|"diagnostic_point"\|"place"`, `inventory_status:"synthetic"\|"documented"`, `assay_status:"pending"\|"available"\|"not_applicable"`, `occurrence_buffer_membership:"inside"\|"outside"\|"unknown"` |
| `MaskResultSchema` *(not exported)* | object | default | `mask:"geological"\|"occurrence_buffer"`, `outcome:"passed"\|"excluded"\|"unknown"`, `reason`, `source` |
| `ShapSchema` | object | default | `output_scale:"raw_margin"\|"probability"`, `explains: z.literal("underlying_classifier_before_pu_adjustment_and_masks")`, `base_value`, `contributions[{feature,label,value,contribution}].min(1)` |
| `PredictionResponseSchema` | object | **`.strict()`** + `superRefine` | `prediction_id`, `provenance`, `asset`, `location\|null`, `validated_scope: literal("Sausar Belt")`, `scope_status`, `scope_reason`, `raw_score\|null`, `final_score\|null`, `mask_requested`, `mask_applied`, `mask_results[]`, `interpretation`, `shap\|null` |
| `ForecastResponseSchema` | object | **`.strict()`** + `superRefine` | `forecast_id`, `provenance`, `scope: literal("MOIL_company_wide")`, `unit: literal("tonnes")`, `issue_date`, `data_cutoff`, `last_observed_month`, `horizon_months: 1\|3\|6\|12`, `interval{level,kind,method}\|null`, `points[{month,point_estimate,lower_bound,upper_bound}]` (1-12) |
| `RiskResponseSchema` | **discriminatedUnion(`value_type`)** | **both members `.strict()`** | base: `risk_id`, `provenance`, `issue_date`, `target_month`, `scope`, `reference_forecast_id`, `event_id: literal("production_below_90_percent_of_forecast")`, `event_definition`, `forecast_threshold_fraction: literal(0.9)`, `calibration_status:"validated"\|"not_validated"`, `limitations[].min(1)`; variant A `value_type:"probability"` + `probability` + `score:null`; variant B `value_type:"score"` + `probability:null` + `score{value,minimum,maximum,higher_means_more_risk}` |
| `ActionResponseSchema` | object | **`.strict()`** + `superRefine` | `action_id`, `provenance`, `rule_id`, `rule_version`, `title`, `recommendation`, `scope`, `trigger_condition{summary,evaluated_at,clauses[{feature,operator:"lt"\|"lte"\|"gt"\|"gte"\|"eq",observed,threshold,unit\|null}].min(1)}`, `review_status:"proposed"\|"reviewed"\|"dismissed"`, `domain_validation:"pending"\|"validated"`, `linked_risk_id\|null`, `evidence[{label,reference}].min(1)`, `reviewed_by\|null`, `reviewed_at\|null` |

**No schema uses `.passthrough()`.** All four response schemas are `.strict()`.
→ **Any extra key from the backend throws.** This is the single biggest integration blocker.

**Cross-field invariants enforced by `superRefine`** (these are product rules, not style — preserve them):

- `PredictionResponseSchema` ([contracts.ts:61-86](lib/contracts.ts#L61)):
  - not `in_scope` ⇒ `raw_score`/`final_score`/`shap` must be `null`, `mask_applied` must be `"none"`, `mask_results` empty
  - `in_scope` ⇒ requires `location` and `raw_score`; `mask_applied` must equal `mask_requested`
  - exactly one `mask_results` entry per active mask
  - any `excluded` ⇒ `final_score === 0` (policy zero)
  - `unknown` and not excluded ⇒ `final_score === null`
  - all passed ⇒ `final_score === raw_score`
- `ForecastResponseSchema` ([contracts.ts:104-120](lib/contracts.ts#L104)): `data_cutoff ≤ issue_date`; `points.length === horizon_months`; months strictly consecutive after `last_observed_month`; `interval === null` ⟺ every `lower_bound === null`
- `ForecastPointSchema` ([contracts.ts:94-100](lib/contracts.ts#L94)): bounds paired, `lower ≤ estimate ≤ upper`
- `ActionResponseSchema` ([contracts.ts:174-180](lib/contracts.ts#L174)): `review_status !== "proposed"` ⟺ both `reviewed_by` and `reviewed_at` non-null

### 4.2 `lib/api/` — one adapter, fixture-backed

**`lib/api/predictions.ts`** (26 lines) — the only file in the directory.

```ts
export interface PredictionClient {
  predict(siteId: string, mask: MaskMode, signal: AbortSignal): Promise<PredictionResponse>;
}
export const predictionClient: PredictionClient = {
  async predict(siteId, mask, signal) {
    await delay(250, signal);
    return PredictionResponseSchema.parse(buildPredictionFixture(siteId, mask));
  },
};
```

| Property | Value |
|---|---|
| Target endpoint | conceptually `POST /predict/point` (never named in code) |
| Wired to | **fixtures** — `buildPredictionFixture()` |
| HTTP calls | **zero** |
| Abort support | yes — `delay()` honours `signal`, unit-tested |
| Integration note | [predictions.ts:21-23](lib/api/predictions.ts#L21) — *"LIVE INTEGRATION: replace ONLY this adapter… Pass signal into fetch. Check res.ok. Do not guess an endpoint from the document or silently fall back to mocks."* |

**There is no adapter for any other endpoint.** No `fetch`, no `axios`, no `NEXT_PUBLIC_API_URL` anywhere in the codebase. The only `process.env` reads are the two Mapbox token vars ([map-canvas.tsx:27](components/explorer/map-canvas.tsx#L27)).

### 4.3 `fixtures/` — every export

**`fixtures/predictions.ts`**

| Export | Shape |
|---|---|
| `SiteFixture` (interface) | `{id, name, location, asset_type, scope_status, inside_buffer:boolean\|null, geological_pass:boolean\|null, raw_score:number\|null, synthetic:boolean}` |
| `DEMO_SITES` | 6 sites: `demo-dump-a` (0.84, inside), `demo-slag-b` (0.62, inside), `demo-dump-c` (0.76, outside), `farmland-control` (0.99, outside, `synthetic:false`), `sandur` (out_of_scope, all null), `bonai` (out_of_scope, all null) |
| `isGhostReserveCandidate(site)` | `(waste_dump ∥ slag_heap) ∧ inside_buffer===true ∧ scope_status==="in_scope"` — **independent of mask state** |
| `buildPredictionFixture(siteId, mask)` | Builds + `.parse()`es a full `PredictionResponse`. Scope gate runs **before** any score ([predictions.ts:58-67](fixtures/predictions.ts#L58)). Throws for unknown id. |

**`fixtures/operations.ts`**

| Export | Shape |
|---|---|
| `historyFixture` | 5 × `{month, tonnes}`, 2026-04..2026-08 |
| `forecastFixture` | `ForecastResponse`, `horizon_months:3`, points 2026-09/10/11, interval level 0.8 |
| `riskFixture` | `RiskResponse` probability variant, `probability: 0.32`, `calibration_status:"not_validated"` |
| `actionFixture` | `ActionResponse`, `review_status:"proposed"`, 1 clause |
| `reviewRegisterFixture` | 4 × `{action, priority, owner, target_date}` — all `proposed` |
| `vitalSignsFixture` | `{latest_production, next_forecast, downside_risk, pending_reviews}` — derived, not hand-written |

**`fixtures/prospectivity-surface.ts`**

| Export | Shape |
|---|---|
| `CellProperties` | `{id, site_id, synthetic:true, raw_score, final_score, mask_applied, mask_excluded, scope_status}` |
| `buildProspectivitySurface(sites, mask)` | `FeatureCollection<Polygon, CellProperties>` — 8-vertex blob per in-scope site; reuses `buildPredictionFixture` so map and inspector cannot disagree |

### 4.4 Field-name mismatches

**Already handled (adapter seam exists):** none. Zero mapping code has been written — `lib/api/predictions.ts` returns a fixture already in frontend shape.

**Still unmapped — every one of these is work to do.** Backend field names from `docs/phase_4/api_contracts.md` v1.6/v1.7 in the teammate's repo.

| Concern | Backend (`GET /forecast`) | Frontend (`ForecastResponseSchema`) | Action |
|---|---|---|---|
| series container | `series[]` *(added v1.7)* | `points[]` | rename |
| point value | `predicted_tonnes` | `point_estimate` | rename |
| lower bound | `lower_ci` / `predicted_lower_ci` | `lower_bound` | rename |
| upper bound | `upper_ci` / `predicted_upper_ci` | `upper_bound` | rename |
| interval level | `ci_level: 0.80` | `interval.level` | nest |
| interval method | *(absent)* | `interval.method` (Nonempty) | **synthesize** |
| id | *(absent)* | `forecast_id` (Nonempty) | **synthesize** |
| issue date | `forecast_date: "2026-09-09"` (date only) | `issue_date` — **needs ISO+offset** | convert |
| data cutoff | *(absent)* | `data_cutoff` required | **synthesize** |
| last observed | *(absent; in `/production/history`)* | `last_observed_month` | cross-fetch |
| provenance | *(absent)* | `provenance{4 fields}` required | **synthesize** |
| extras | `components{}`, `model{}`, `accuracy_at_horizon{}`, `target_period`, `horizon_months` | — | **`.strict()` REJECTS** |

| Concern | Backend (`GET /shortfall/risk`) | Frontend (`RiskResponseSchema`) | Action |
|---|---|---|---|
| probability | `shortfall_probability` | `probability` | rename |
| discriminator | *(absent)* | `value_type:"probability"` | **synthesize** |
| target month | `forecast_month` | `target_month` | rename |
| definition | `shortfall_definition` | `event_definition` | rename |
| event id | *(implicit)* | literal `production_below_90_percent_of_forecast` | **synthesize** |
| threshold | `shortfall_threshold_tonnes` (absolute t) | `forecast_threshold_fraction: literal(0.9)` | **different quantity** |
| calibration | `model_metadata{roc_auc, pr_auc, base_rate,…}` | `calibration_status` enum | derive |
| limitations | *(absent)* | `limitations[].min(1)` | **synthesize** |
| SHAP | `feature_contributions[9]{feature_name,human_label,value,display_value,shap_contribution,direction}` + `shap_base_value` | `ShapSchema{output_scale,explains,base_value,contributions[{feature,label,value,contribution}]}` | restructure |
| id / ref | *(absent)* | `risk_id`, `reference_forecast_id` | **synthesize** |

| Concern | Backend (`GET /recommendations`) | Frontend (`ActionResponseSchema`) | Action |
|---|---|---|---|
| card id | `id` | `action_id` | rename |
| body | `rationale` | `recommendation` | rename |
| trigger | `triggered_by[{signal,value,display_value,shap_contribution}]` | `trigger_condition.clauses[{feature,operator,observed,threshold,unit}]` | **restructure — backend has no operator/threshold** |
| rule id | *(uses `id`)* | `rule_id` + `rule_version` | **synthesize** |
| review lifecycle | **absent entirely** | `review_status`, `reviewed_by`, `reviewed_at`, `domain_validation` | **backend gap — §5.2** |
| extras | `action_type`, `equipment_referenced[]`, `priority`, `driver`, `driver_label`, `confidence` | — | **`.strict()` REJECTS** |

| Concern | Backend (`POST /predict/point`) | Frontend (`PredictionResponseSchema`) | Action |
|---|---|---|---|
| raw score | `raw_score` ✅ | `raw_score` ✅ | **match** |
| screened score | `final_score` ✅ | `final_score` ✅ | **match** |
| mask applied | `mask_applied` ✅ | `mask_applied` ✅ | **match** |
| mask decision | `mask_decision` (single string) | `mask_results[]` (per-mask `{mask,outcome,reason,source}`) | expand |
| score | `prospectivity_score` | *(no equivalent)* | **`.strict()` REJECTS** |
| extras | `predicted_type`, `uncertainty`, `features_extracted{}`, `shap_top5[]`, `lat`, `lon`, `prediction_id:int` | `prediction_id` is `Nonempty` **string** | type conflict |
| asset/scope | *(absent)* | `asset{6}`, `scope_status`, `scope_reason`, `validated_scope`, `interpretation` | **synthesize — no backend source** |

**Summary:** the raw-vs-screened score semantics align exactly. Everything else needs an adapter, and `.strict()` means the adapter must **pick** fields, never spread.

---

## 5. BACKEND INTEGRATION READINESS

### 5.1 Endpoint matrix

| Endpoint | UI surface | Adapter? | Schema match | Known mismatch |
|---|---|---|---|---|
| `GET /production/history` | `ProductionChart` history series; `VitalSigns` "Latest production" | ❌ none | ❌ | `historyFixture` is `{month,tonnes}`; backend gives `{report_month, mh_qty_tonnes, mp_qty_tonnes, mh_plus_mp_qty_tonnes, all_india_qty_tonnes, extraction_method}`. No frontend Zod schema exists for this at all. |
| `GET /forecast` | `ForecastRiskPanel`, `ProductionChart`, `VitalSigns` | ❌ none | ❌ | 12 field renames/synthesis — §4.4. Backend returned a **single point** until v1.7 added `series[]`; frontend requires `points.length === horizon_months`. |
| `GET /forecast/history` | *(nothing consumes it)* | ❌ none | — | No UI surface. Candidate for the actual-vs-predicted overlay in `ProductionChart`. |
| `GET /shortfall/risk` | `RiskGauge`, `VitalSigns` "Downside risk", `ShapBarChart` | ❌ none | ❌ | 10 renames + `value_type` discriminator + `limitations[]` must be synthesized — §4.4 |
| `GET /dashboard/summary` | `VitalSigns` (4 tiles) — best single fit | ❌ none | ❌ | No frontend schema. Backend also returns `data_provenance` (v1.7) which **must** be surfaced — see §5.3. |
| `GET /recommendations` | `ReviewRegister`, `ActionEvidence`, `ActionsWorkbench` | ❌ none | ❌ | Review lifecycle absent backend-side — §5.2 |
| `GET /prospectivity/heatmap` | `MapCanvas` / `TokenlessMapCanvas` fill layers | ❌ none | ❌ | Backend returns a **row-major score lattice** (`scores[][]`, `grid{n_cols,n_rows,cell_*_deg,origin:"top_left"}`); frontend consumes a **GeoJSON FeatureCollection of polygons**. Needs a grid→GeoJSON (or image-overlay) converter. `null` ≠ `0.0` must survive — `prospectivity.layers.json` already filters `["==",["typeof",["get","final_score"]],"number"]`, which correctly drops nulls. |
| `POST /predict/point` | `SiteInspector` via `usePrediction()` | ✅ **`lib/api/predictions.ts`** | ⚠ partial | Only endpoint with a seam. `raw_score`/`final_score`/`mask_applied` align; `asset`/`scope_status`/`interpretation` have no backend source; `.strict()` rejects 7 backend extras. |
| `GET /masks` | `MaskExplanationPanel` `reason`/`source` text | ❌ none | ❌ | Currently hardcoded fixture strings. Backend `describe()` returns `{id,label,source,description,geojson_path}`. |
| `GET /mines` | *(nothing consumes it)* | ❌ none | — | No UI surface anywhere. 10 MOIL mines unused by the frontend. |

**Adapters existing: 1 of 10.**

### 5.2 Blocking backend gaps

1. **No review workflow.** Backend `/recommendations` has no `review_status`/`reviewed_by`/`reviewed_at`/`domain_validation`, and the API is entirely read-only (no write endpoint, no actions table). `ActionsWorkbench` + `ReviewRegister` + the `ActionResponseSchema` `superRefine` are all built around that lifecycle.
2. **`/predict/bbox` is broken backend-side** (returns a non-griddable, partly out-of-bbox point set). **Confirmed: the frontend never references it.** `grep` for `predict/bbox` across `app components lib hooks stores fixtures` returns zero hits. The map path is `buildProspectivitySurface` → will become `/prospectivity/heatmap`. ✅ No action needed.
3. **No `/production/history` or `/mines` consumer.** Two live endpoints have no UI.

### 5.3 CORS port status

| | Value |
|---|---|
| Frontend dev port | **3001** (`npm run dev:sih` → `next dev -p 3001`, [package.json:7](package.json#L7)) |
| Alternate | 3000 (`npm run dev`), 3100 (Playwright webServer) |
| Backend allowlist **as pushed** | 3000, 5173, 8080 (+127.0.0.1) — **3001 NOT included** |
| Backend allowlist **after local fix** | 3000, 3001, 3002, 5173, 8080 + `CORS_EXTRA_ORIGINS` |

⚠ **Playwright runs on 3100, which is in neither allowlist.** If e2e specs ever hit the live API they will fail on CORS. Either add 3100 to the backend, or keep e2e fixture-backed.

---

## 6. MAPBOX STATE

### 6.1 Token handling

[map-canvas.tsx:27](components/explorer/map-canvas.tsx#L27):
```ts
const publicToken = (process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? process.env.NEXT_PUBLIC_MAPBOX_ACCESS_TOKEN ?? "").trim();
```
Two accepted names, `.trim()`ed so whitespace-only counts as absent. Read at **module scope** — a token added at runtime will not be picked up without a reload. No `.env.local` exists in the repo.

### 6.2 Renderer selection

[map-canvas.tsx:50-52](components/explorer/map-canvas.tsx#L50): `publicToken ? <MapboxCanvas/> : <TokenlessMap/>`.
`TokenlessMap` = `dynamic(() => import("./tokenless-map-canvas"), {ssr:false})` — **MapLibre GL**, NASA Blue Marble raster context. Both renderers consume the identical `MapCanvasProps`, the identical `buildProspectivitySurface` output and the identical `prospectivityLayers()` spec.
`ExplorerWorkspace` additionally wraps `MapCanvas` in `dynamic(…, {ssr:false})` ([explorer-workspace.tsx:17](components/explorer/explorer-workspace.tsx#L17)) — required because Next 14 forbids `ssr:false` in a Server Component.

### 6.3 `registerMaskPattern`

[lib/map/register-mask-pattern.ts](lib/map/register-mask-pattern.ts) — builds an 8×8 RGBA sprite named `excluded-hatch`; 2 opaque / 6 transparent pixels per diagonal (`(x+y)%8 < 2`), colour `#B9C4CC`. Idempotent via `hasImage()`. Called **inside `installLayers`, before `addLayer`** ([map-canvas.tsx:104](components/explorer/map-canvas.tsx#L104)), and `installLayers` is bound to `style.load` ([map-canvas.tsx:173](components/explorer/map-canvas.tsx#L173)) — correct, because a style change drops registered images. Doc comment: *"Never apply this pattern to unknown scope or use it as UI decoration."*

### 6.4 Layer spec

Committed at `public/styles/prospectivity.layers.json`, loaded via `prospectivityLayers(sourceType)` ([lib/map/prospectivity-layers.ts](lib/map/prospectivity-layers.ts)), which `structuredClone`s and deletes `source-layer` for GeoJSON mode (keeping it would silently prevent rendering).

| Layer id | Filter | Paint |
|---|---|---|
| `prospectivity-screened` | `in_scope` ∧ `mask_excluded===false` ∧ `typeof final_score === "number"` ∧ `0 ≤ score ≤ 0.99` | interpolate `#555F64 → #BFAB84 → #DCA55E → #EC803A → #FF5B26`, opacity .65 |
| `prospectivity-excluded` | `in_scope` ∧ `mask_excluded===true` | `fill-pattern: excluded-hatch`, opacity 1 |
| `prospectivity-outside-scope` | `scope_status === "out_of_scope"` | `#697680`, opacity .28 |

Runtime-added layers not in the JSON: `prediction-outlines` (line), `site-selection` (circle, feature-state driven), `fixture-site-points` (circle, non-waste), `fixture-waste-sites` (symbol, canvas-drawn `waste-diamond` sprite).

⚠ The `MapLegend` ramp is a **hardcoded duplicate** of the JSON ramp ([map-legend.tsx:3](components/explorer/map-legend.tsx#L3)). Two sources of truth — they will drift.

### 6.5 Basemap fallback & failure handling

| Trigger | Behaviour | Code |
|---|---|---|
| No token | MapLibre renderer + persistent `.map-token-notice` banner | [map-canvas.tsx:51,252](components/explorer/map-canvas.tsx#L51) |
| `mapboxgl.supported()` false | `failure` set, "WebGL is unavailable… Use the site list below." | [map-canvas.tsx:67](components/explorer/map-canvas.tsx#L67) |
| Constructor throws | `failure` set, map skipped | [map-canvas.tsx:83](components/explorer/map-canvas.tsx#L83) |
| `error` event | `failure` banner; token errors also clear `ready` | [map-canvas.tsx:149](components/explorer/map-canvas.tsx#L149) |
| 15 s elapsed without `load` | "Satellite tiles are taking too long…" | [map-canvas.tsx:92](components/explorer/map-canvas.tsx#L92) |
| Any of the above | Static coordinate-plot fallback with clickable site buttons at `projectedPosition()`, full lat/lon graticule labels | [map-canvas.tsx:228-250](components/explorer/map-canvas.tsx#L228) |

The site list below the map is always rendered and always usable — the map is never the only path to a selection.

### 6.6 Warm-up / cold-start

**None.** No prefetch, no `/prospectivity/heatmap` warm call, no skeleton timing logic beyond the 15 s timeout. Backend documents a **5 s warm / 45 s cold** SLA for the heatmap with server-side startup warming of three viewports. The frontend has no matching loading affordance — a cold first paint would look hung. **This needs a loading state before integration.**

Diagnostics exposed for e2e on the root div ([map-canvas.tsx:226](components/explorer/map-canvas.tsx#L226)): `data-ready`, `data-rendered-cells`, `data-rendered-excluded`, `data-rendered-waste` — computed from `queryRenderedFeatures` on `idle`, i.e. **actually rendered** counts, not input counts.

---

## 7. STATE & BEHAVIOR

### 7.1 Zustand

One store: `stores/explorer-store.ts` (21 lines), built with `createStore` from **`zustand/vanilla`** (not the React `create`).

```ts
interface ExplorerStore {
  activeMask: MaskMode;          // initial "both"
  ghostOnly: boolean;            // initial false
  selectedSiteId: string | null; // initial "demo-dump-a"
  setMask(mask); setGhostOnly(enabled); selectSite(id);
}
```

Instantiated **per provider mount** via `useState(createExplorerStore)` ([explorer-provider.tsx:11](components/explorer/explorer-provider.tsx#L11)) and shared through React context — deliberately, so an SSR request never shares module-level state between users. Unit-tested at [tests/unit/contracts.test.ts:56-65](tests/unit/contracts.test.ts#L56).

Provider is mounted in `app/(workspace)/layout.tsx`, so **all four workspace views share one store** — but only Explorer reads it.

### 7.2 URL state

- **Only** `/actions?review=<action_id>` ([actions/page.tsx:4-5](app/(workspace)/actions/page.tsx#L4)), read from `searchParams` server-side and passed as `initialId`, with `key={initialId ?? "default"}` to force remount.
- `ReviewRegister` links to it via `<Link href={"/actions?review=" + action.action_id}>` ([review-register.tsx:27](components/operations/review-register.tsx#L27)).
- **Mask mode, ghost toggle and site selection are NOT in the URL** — no deep-linking, no shareable Explorer state, lost on reload.
- `usePathname()` used for nav highlighting only. `useRouter`/`useSearchParams` unused.

### 7.3 Mask toggle logic

Two independent switches collapse into one enum ([explorer-workspace.tsx:39-44](components/explorer/explorer-workspace.tsx#L39)):
```ts
const geological = mode === "geological" || mode === "both";
const occurrence = mode === "occurrence_buffer" || mode === "both";
const next = g && o ? "both" : g ? "geological" : o ? "occurrence_buffer" : "none";
```
Changing a mask re-renders the map source without recreating the Mapbox instance ([map-canvas.tsx:200-207](components/explorer/map-canvas.tsx#L200)) and **deliberately preserves the camera** ([map-canvas.tsx:223](components/explorer/map-canvas.tsx#L223)).

### 7.4 Ghost Reserve toggle logic

- Predicate ([fixtures/predictions.ts:29-35](fixtures/predictions.ts#L29)): `(historical_waste_dump ∨ slag_heap) ∧ inside_buffer===true ∧ scope_status==="in_scope"`.
- **Explicitly independent of mask state** — comment at [explorer-workspace.tsx:55-56](components/explorer/explorer-workspace.tsx#L55) and asserted at [contracts.test.ts:56](tests/unit/contracts.test.ts#L56).
- Turning Ghost ON while a non-candidate is selected **clears the selection** ([explorer-store.ts:17-20](stores/explorer-store.ts#L17)).
- Searching for a filtered-out in-scope site shows a notice rather than silently failing ([explorer-workspace.tsx:65-68](components/explorer/explorer-workspace.tsx#L65)).
- `visibleSites` is computed **once** and passed to both map and list, so they cannot disagree.
- Source comment warns: live membership must come from backend PostGIS metric distance — *"do not approximate kilometres using degrees."*

### 7.5 Scope check (Sandur / Bonai)

**Entirely fixture-driven — there is no algorithm.**

- `sandur` and `bonai` are rows in `DEMO_SITES` with `scope_status:"out_of_scope"`, `location:null`, all scores `null` ([predictions.ts:25-26](fixtures/predictions.ts#L25)).
- `buildPredictionFixture` gates **before** any score is produced ([predictions.ts:58-67](fixtures/predictions.ts#L58)), returning `scope_reason: "Outside validated scope (Sausar Belt)"`, `raw_score:null`, `final_score:null`, `shap:null`, `mask_applied:"none"`, `mask_results:[]`.
- `SiteInspector` renders the `ShieldAlert` panel with `data-testid="scope-message"` and **never** a 0% ([site-inspector.tsx:44](components/explorer/site-inspector.tsx#L44)).
- Two buttons hard-wire access to them ([explorer-workspace.tsx:104](components/explorer/explorer-workspace.tsx#L104)).
- `PredictionResponseSchema` **rejects** an out-of-scope response carrying any score — `safeParse({...response, raw_score: 0.001})` is `false` ([contracts.test.ts:14](tests/unit/contracts.test.ts#L14)).
- Source comment ([predictions.ts:59-60](fixtures/predictions.ts#L59)): *"Live mode must use the backend's versioned validated-domain predicate. A bounding box or a blacklist of two town names is not sufficient."*

### 7.6 Request lifecycle

`hooks/use-prediction.ts` keys on `${selectedSiteId}:${activeMask}`, aborts the previous request on change, and **discards mismatched results before the next effect runs** ([use-prediction.ts:26](hooks/use-prediction.ts#L26)) — so a slow response for a deselected site can never paint. Returns `{data, error, loading, selected}`.

---

## 8. TESTS & BUILD HEALTH

### 8.1 `tsc --noEmit` — ✅ **PASS** (exit 0, no diagnostics)

### 8.2 `next build` — ✅ **PASS** (exit 0)

```
Route (app)                              Size     First Load JS
┌ ○ /                                    54.3 kB         142 kB   ← HeroSection, NOT Command Center
├ ○ /_not-found                          873 B          88.7 kB
├ ƒ /actions                             2.96 kB         127 kB
├ ○ /explorer                            17.5 kB         262 kB
├ ○ /icon.svg                            0 B                0 B
└ ○ /production                          2.69 kB         247 kB
+ First Load JS shared by all            87.9 kB
```
**Note:** the build emits **no warning** about the `/` collision. `54.3 kB` at `/` is the tell — the Command Center is ~2.5 kB.

### 8.3 `vitest run` — ✅ **15/15 PASS** (2 files, 211 ms)

`tests/unit/contracts.test.ts` — 11 tests, pinning:
1-2. Sandur & Bonai carry no score, and a manufactured `0.001` is **rejected** by the schema
3. Farmland false positive keeps `raw_score 0.99` while `final_score` goes to `0` under `both`; setting `final_score:0.99` on a masked response is rejected
4. Score cap `≤0.99` enforced; empty and duplicated `mask_results` rejected
5. Ghost filter yields exactly `["demo-dump-a","demo-slag-b"]`; `null` buffer and `unknown` scope excluded
6. Inverted / one-sided / null-interval forecast metadata rejected
7. Future `data_cutoff` and missing forecast months rejected
8. Risk `probability` and `score` mutually exclusive; `probability: 32` (not a fraction) rejected
9. `review_status:"reviewed"` without audit fields rejected
10. Two stores do not share state; ghost filtering independent of masks
11. A superseded mock request rejects with `AbortError`

`tests/unit/prospectivity-surface.test.ts` — 4 tests, pinning:
1. Diagnostic cell keeps `raw_score .99` / `final_score 0` / `mask_excluded true` under `both`, and `.99/.99/false` under `none`; Sandur/Bonai never become zero-score cells (4 features, not 6)
2. Ghost-filtered surface = exactly the two eligible assets
3. `prospectivityLayers("geojson")` has no `source-layer`; `("vector")` keeps `prediction_cells`; excluded layer uses `excluded-hatch`
4. `vitalSignsFixture.pending_reviews` derives from the same register users see; 4 unique action ids

### 8.4 Playwright — `tests/e2e/`, 3 spec files, 6 tests

Config: `testDir ./tests/e2e`, `fullyParallel:false`, baseURL `http://127.0.0.1:3100`, viewport 1920×1080, webServer `next dev -p 3100` with **both Mapbox token vars forced empty** (so e2e always exercises the MapLibre tokenless path).

| Spec | Test | Flow covered |
|---|---|---|
| `briefing.spec.ts:18` | Briefing keeps uncertainty, horizon and demo provenance visible | `/` → risk meter `aria-valuenow=32`, vital-risk `32%`, register 5 rows, synthetic disclaimer, horizon switch 3→1 month, review links, "No reviewed actions…" empty state, `/production` interval caveat, zero console errors |
| `explorer.spec.ts:18` | Explorer truth states and mask/selection synchronization | token notice, `data-ready`, rendered cells 4 / excluded 2 / waste 3, Ghost ON → cells 2 / waste 2, mask none → final `0.99` excluded 0, mask both → raw `0.99` final `0.00` excluded 2, slag selection, Sandur scope message with **no** raw-score node, SHAP tab, no horizontal overflow at two viewports, zero console errors |
| `interaction-regression.spec.ts:3` | Search, evidence and masks preserve independent truth states | no-result message, Escape clears, ghost-filter notice, scope message, clear selection, slag caveat, mask-off panel text, SHAP-absent message |
| `interaction-regression.spec.ts:47` | Review register links preserve selected evidence and never create approvals | `/actions?review=demo-action-04` deep link, filter counts, "No reviewed actions. The demonstration does not fabricate approvals.", unknown review id fallback |
| `interaction-regression.spec.ts:66` | Print includes closed evidence tables and restores the reading state | `<details>` force-open before print, `data-print-invoked`, restore after `afterprint` |
| `interaction-regression.spec.ts:89` | Every workspace view remains navigable at a narrow viewport | all four routes at narrow width |

**Current result — run fresh during this audit (1.3 min, `PLAYWRIGHT_CHANNEL=chrome`): 4 failed, 2 passed.**

```
  4 failed
    briefing.spec.ts:18               > Briefing keeps uncertainty, horizon and demo provenance visible
    interaction-regression.spec.ts:47 > Review register links preserve selected evidence...
    interaction-regression.spec.ts:66 > Print includes closed evidence tables...
    interaction-regression.spec.ts:89 > Every workspace view remains navigable at a narrow viewport
  2 passed
    explorer.spec.ts:18               > Explorer truth states and mask/selection synchronization
    interaction-regression.spec.ts:3  > Search, evidence and masks preserve independent truth states
```

**Every failure traces to 10.1 - none is an independent defect.** The two passing specs are precisely the two that never visit `/`.

The clearest signature is `interaction-regression.spec.ts:102`, which times out on:
```
waiting for getByRole('navigation', {name:'Main navigation'})
                .getByRole('link', {name:'Prospectivity', exact:true})
```
There is no `Main navigation` landmark on `/` at all, because `HeroSection` renders **outside** the `(workspace)` route group and therefore never receives `AppShell`. Fixing the collision should restore all four.

Note: the shell exit code was `0` only because the command was piped to `tail`; the Playwright reporter itself reported 4 failures. Do not trust `$?` through a pipe in CI - use `set -o pipefail`.

### 8.5 Verification summary

| Check | Command | Result |
|---|---|---|
| Typecheck | `npx tsc --noEmit` | PASS, exit 0, no diagnostics |
| Build | `npx next build` | PASS, exit 0, 6 routes emitted |
| Unit | `npx vitest run` | PASS, 15/15, 211 ms |
| E2E | `PLAYWRIGHT_CHANNEL=chrome npx playwright test` | **FAIL, 2/6 passed** |

All four were run fresh during this audit against the unmodified working tree.

---

## 9. CHANGELOG SINCE LAST KNOWN STATE

Chronological, by mtime. "Last known state" = the Sausar Survey / graphite-oxide implementation archived in `docs/DESIGN_RESEARCH.md`.

### Sep 9, 14:03-19:36 — Earth Observatory conversion
- `app/globals.css` rewritten — full token replacement (§2.1)
- `components/operations/survey-outlook.tsx`, `action-evidence.tsx`, `production-chart.tsx`, `risk-gauge.tsx` restyled
- `components/explorer/map-legend.tsx`, `explorer-workspace.tsx` updated
- `app/(workspace)/layout.tsx` — `operations.css` import moved here so all four routes get it

### Sep 9, 19:50-19:55 — dependency-free motion system **(now orphaned)**
- **Added:** `components/motion/specimen-drift.tsx`, `odometer.tsx`, `reveal.tsx`
- IntersectionObserver + CSS custom properties + rAF; no libraries
- `tests/e2e/briefing.spec.ts`, `explorer.spec.ts` gained a `settle()` scroll helper

### Sep 9, 20:19-20:35 — GSAP motion system added in parallel **(mostly orphaned)**
- **Added deps:** `gsap ^3.15.0`, `lenis ^1.3.26`, `splitting ^1.1.0`, `@types/splitting`
- **Added:** `components/motion/` → `eyebrow-bracket`, `plus-pattern`, `preloader`, `text-fill`, `text-reveal`, `magnetic-button`, `page-transition`, `theme-section`, `line-plus-divider`, `nav-link`
- **Added:** `lib/animations/` → `gsap-register.ts`, `text-split.ts`, `smooth-scroll.tsx`
- **Wired:** only `TextReveal` + `EyebrowBracket`, only into `forecast-risk-panel.tsx` (20:25)

### Sep 10, 11:52-12:58 — shell/asset changes
- `app/layout.tsx` **rewritten to 11 lines — the `.motion-ready` gate script was REMOVED** (§10.5)
- `components/shell/mineral-specimen.tsx` **rewritten** — inline SVG + onError fallback replaced with a bare `<img src="/images/manganese-specimen.webp">` (§10.3)
- `components/shell/app-shell.tsx` restyled to `.observatory-masthead`
- `components/explorer/map-presentation.css` **added** (153 lines), imported by both map canvases
- `components/explorer/map-canvas.tsx`, `tokenless-map-canvas.tsx` updated
- `components/operations/vital-signs.tsx`, `review-register.tsx`, `actions-workbench.tsx`, `operations.css` updated — register rows gained `evidenceRef` + rAF `scrollIntoView`/`focus`, `aria-controls="selected-action-evidence"`, `ArrowUpRight`→`ArrowRight`
- `tests/e2e/interaction-regression.spec.ts` updated
- **`app/page.tsx` ADDED (12:58)** — introduced the route collision (§10.1)
- **Assets added:** `public/hero-mining-1.jpg`, `hero-mining-2.jpg`, `hero-video.mp4` (3.5 MB), `hero-scroll.mp4` (2.3 MB), `images/manganese-specimen-original.png` (2.8 MB) — **all unreferenced**

### Sep 11, 11:58 — hero
- **`components/hero-section.tsx` ADDED** — GSAP ScrollTrigger, 300vh runway, `scrub:1.5`, two-image crossfade, `prefers-reduced-motion` early return
- **Assets added:** `public/test-img-1.jpg`, `test-img-2.jpg` — **carry a visible "KlingAI 3.0" watermark** (§10.4)

### Deleted since last known state
None. No component was removed — the old motion system was superseded but left in place, producing two parallel orphaned systems.

---

## 10. PENDING / KNOWN-BROKEN

### 10.1 🔴 Route collision — the Command Center is unreachable
[app/page.tsx](app/page.tsx) and [app/(workspace)/page.tsx](app/(workspace)/page.tsx) both resolve to `/`. Route groups do not affect URL paths, so Next.js silently serves the **non-grouped** file. No build error, no dev warning.
**Consequences:** the dashboard never renders; `AppShell` nav "Command Center" leads to the hero; the hero renders **without** masthead, nav or scope strip (it is outside `(workspace)`); 4 of 6 e2e specs fail.
**Fix options:** (a) delete `app/page.tsx`, move the hero to `app/(marketing)/landing/page.tsx`; (b) delete the hero entirely; (c) make the hero a component *inside* `(workspace)/page.tsx` above `VitalSigns`. **Option (a) or (b) is required before integration.**

### 10.2 🔴 JSX comment renders as literal on-screen text
[components/hero-section.tsx:61](components/hero-section.tsx#L61):
```jsx
// The sticky wrapper keeps the view pinned to the screen while scrolling through the container
<div className="sticky top-0 w-full h-screen overflow-hidden">
```
A bare `//` sitting directly between JSX elements is a **text node**, not a comment. It renders visibly at the top of `/`. (Line 58's comment is fine — it sits inside the `return (` parenthesis before the root element.) Fix: wrap in `{/* … */}`.

### 10.3 🔴 Broken image on the Command Center
[components/shell/mineral-specimen.tsx:4](components/shell/mineral-specimen.tsx#L4) requests `/images/manganese-specimen.webp`. `public/images/` contains only `manganese-specimen-original.png` — **different name and extension**. Guaranteed 404 with **no `onError` fallback** (the previous inline-SVG fallback was removed on Sep 10). Will show a broken-image icon the moment `/` is fixed.

### 10.4 🟠 Third-party watermark in the hero
`public/test-img-1.jpg` / `test-img-2.jpg` carry a visible **"KlingAI 3.0"** watermark, bottom-right. They are the full-bleed background of `/`. Filenames literally begin `test-img`, so these are almost certainly placeholders.

### 10.5 🟠 The motion gate is dead — motion never runs
`app/layout.tsx` was rewritten to 11 lines and **no longer injects the synchronous `<head>` script that adds `.motion-ready` to `<html>`**. But the CSS and five components still test for it:
`globals.css:290`, `text-reveal.tsx:32,77,95,98`, `text-fill.tsx:25`, `odometer.tsx:23`, `reveal.tsx:21`.
**Fails safe** — `[data-reveal]{opacity:1;transform:none}` is unconditional ([globals.css:285](app/globals.css#L285)), so nothing is hidden and no evidence is lost. But every reveal/odometer/text animation now takes the "show immediately" branch. Either restore the script or delete the dead branches.

### 10.6 🟠 Two orphaned motion systems + unused dependencies
11 of 13 `components/motion/` files and all 3 `lib/animations/` files have **zero importers**. `lenis` and `splitting` are installed but reachable only from orphaned files; `gsap` is reachable only from `hero-section.tsx` and three orphans. ~2 systems of dead code.

### 10.7 🟠 `MapLegend` duplicates the colour ramp
[map-legend.tsx:3](components/explorer/map-legend.tsx#L3) hardcodes `["#555F64","#BFAB84","#DCA55E","#EC803A","#FF5B26"]`, duplicating `public/styles/prospectivity.layers.json`. Also note the backend warns ~24.5% of v6 cells score ≥0.90, so a **linear** ramp will saturate a quarter of the map — the legend and the layer spec must be changed together.

### 10.8 🟡 Hardcoded dates and figures in Production view
[production/page.tsx:18-24](app/(workspace)/production/page.tsx#L18): "September"/"2026", "1 September 2026 · UTC" ×2, "August 2026" — all string literals, not derived from `forecastFixture`. `VitalSigns` similarly hardcodes `"80% bounds 108–142k t"` ([vital-signs.tsx:11](components/operations/vital-signs.tsx#L11)) rather than formatting `next_forecast`. These will silently lie once live data arrives.

### 10.9 🟡 Mock that must become live
[lib/api/predictions.ts:20-23](lib/api/predictions.ts#L20) — the 250 ms `delay()` + `buildPredictionFixture` is the single mock seam. Everything else imports fixtures **directly** from components (`vital-signs.tsx`, `survey-outlook.tsx`, `review-register.tsx`, `actions-workbench.tsx`, and both `page.tsx` files), bypassing any adapter layer. **Nine more adapters need to be created, and ~8 direct fixture imports rewired.**

### 10.10 🟡 Stale favicon
`app/icon.svg` is still Survey-Edition maroon `#662638` / cream `#fff9f1`.

### 10.11 🟡 No Explorer state in the URL
Mask mode, ghost toggle and selection are memory-only. No deep-linking, lost on reload. Only `/actions?review=` is URL-addressable.

### 10.12 🟡 No loading affordance for a slow heatmap
§6.6 — backend documents 45 s cold. Frontend has no skeleton for it.

### 10.13 ⚪ Dead prop
`MapCanvasProps.onUnmappedClick` fires a notice telling the user arbitrary point queries need the live API — correct behaviour today, but it becomes the **primary** interaction once `POST /predict/point` is live. Currently a dead end by design.

---

## 11. SIMPLE-UI STRIP LIST

### 11.1 Minimum viable connected demo — KEEP

**Routing / shell (3)**
`app/layout.tsx` · `app/(workspace)/layout.tsx` · `components/shell/app-shell.tsx`

**Pages (4)** — after fixing §10.1
`app/(workspace)/page.tsx` · `explorer/page.tsx` · `production/page.tsx` · `actions/page.tsx`

**Data spine (6)**
`lib/contracts.ts` · `lib/api/predictions.ts` (+ 9 new sibling adapters) · `lib/utils.ts` · `hooks/use-prediction.ts` · `stores/explorer-store.ts` · `fixtures/*` (keep until each endpoint is wired, then delete per-endpoint)

**Functional components (17)**
`explorer-provider` · `explorer-workspace` · `map-canvas` · `tokenless-map-canvas` · `map-legend` · `site-inspector` · `shap-bar-chart` · `vital-signs` · `forecast-risk-panel` · `production-chart` · `risk-gauge` · `review-register` · `action-evidence` · `actions-workbench` · `ui/button` · `ui/switch` · `ui/tabs`

**Map support (3)**
`lib/map/prospectivity-layers.ts` · `lib/map/register-mask-pattern.ts` · `public/styles/prospectivity.layers.json`

**CSS (3)** — keep all three; `operations.css` and `map-presentation.css` carry layout, not just paint. Stripping them collapses the grids.
`app/globals.css` · `components/operations/operations.css` · `components/explorer/map-presentation.css`

### 11.2 Temporarily disable

| Item | Action | Risk |
|---|---|---|
| `components/hero-section.tsx` + `app/page.tsx` | **delete both** (fixes §10.1, §10.2, §10.4 at once) | none — nothing imports them |
| `components/shell/mineral-specimen.tsx` | remove the `<MineralSpecimen/>` call at [page.tsx:30](app/(workspace)/page.tsx#L30) | none — fixes §10.3 |
| `components/motion/` (all 13) | delete dir; drop `TextReveal`/`EyebrowBracket` usage in `forecast-risk-panel.tsx` (2 import lines + 2 JSX wrappers) | low — only 2 are wired, and both fail-safe to static already |
| `lib/animations/` (all 3) | delete dir | none — 0 importers |
| `gsap`, `lenis`, `splitting`, `@types/splitting` | uninstall after the two deletes above | none |
| `components/operations/print-briefing.tsx` | remove 3 call sites | **breaks `interaction-regression.spec.ts:66`** |
| `components/operations/survey-outlook.tsx` (`SurveyOutlook`) on Explorer | remove [explorer-workspace.tsx:107](components/explorer/explorer-workspace.tsx#L107) | low — duplicates `/production` content; keep `KeyConstraints` for `/production` |
| `ReviewRegister` duplicate on `/explorer` | remove [explorer-workspace.tsx:109](components/explorer/explorer-workspace.tsx#L109) | low — same data shown on 3 views |
| `.observatory-hero` block, `.forecast-reading` grid, `KeyConstraints`, `.instrument-rail` static dates | strip copy blocks | **removes §10.8 hardcoded-date liability** |
| `public/` unused media (hero-*.jpg/mp4, test-img-*.jpg, manganese-specimen-original.png) | delete (~9 MB) | none — 0 references after the hero delete |

### 11.3 Do NOT strip — these are correctness, not decoration

- Every `superRefine` in `lib/contracts.ts` — they are the honesty invariants (null ≠ zero, scope gating, no fabricated approvals).
- `prospectivity-excluded` hatch layer + `registerMaskPattern` — distinguishes "excluded by policy" from "low score".
- The `["==",["typeof",["get","final_score"]],"number"]` filter — this is what keeps `null` off the colour scale.
- `SiteInspector`'s out-of-scope branch ([site-inspector.tsx:44](components/explorer/site-inspector.tsx#L44)) and the `data-testid="scope-message"` node.
- The "No reviewed actions. The demonstration does not fabricate approvals." empty state ([review-register.tsx:30](components/operations/review-register.tsx#L30)).
- `map-canvas.tsx`'s fallback chain (§6.5) — the site list must remain reachable without WebGL.
- The `usePrediction` key/abort logic — prevents stale paint on fast mask toggling.
- All synthetic-data labels. Once `/dashboard/summary` returns `data_provenance.synthetic === true`, that must be surfaced as a persistent banner.

### 11.4 Suggested integration order

1. Fix §10.1 (delete `app/page.tsx` + hero). Re-run e2e — expect 6/6.
2. Add `NEXT_PUBLIC_API_BASE_URL`; build `lib/api/client.ts` with `fetch` + `res.ok` + abort passthrough.
3. `GET /dashboard/summary` → `VitalSigns`. Smallest surface, exercises CORS, and immediately surfaces `data_provenance`.
4. `GET /forecast` + `GET /production/history` → `ProductionChart` / `ForecastRiskPanel`.
5. `GET /shortfall/risk` → `RiskGauge` + `ShapBarChart`.
6. `GET /recommendations` → `ReviewRegister` / `ActionsWorkbench` (review lifecycle still open — §5.2).
7. `GET /prospectivity/heatmap` → map (needs the grid→GeoJSON converter + loading state).
8. `POST /predict/point` → `SiteInspector` (replace the existing adapter body only).
9. `GET /masks` → `MaskExplanationPanel` text.
10. Only then: restore or rebuild the visual layer.

**Relax `.strict()` to `.passthrough()` per schema as you wire each endpoint**, or write explicit field-picking adapters. Do not spread backend responses into these schemas — every one of the ten will throw on extra keys.
