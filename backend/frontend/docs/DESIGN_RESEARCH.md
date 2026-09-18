# Mineral Intelligence Workbench — Graphite / Oxide
> Archived visual direction. The user-selected **Sausar survey** mockup supersedes the colors and layouts in this study. See ../DESIGN.md and app/globals.css for the implemented burgundy/cream editorial system. Research and evidence-boundary findings remain reference material.

Research, design specification and implementation · 8 September 2026

## 1. Research summary

**Decision:** use graphite for navigation and actions, oxide for Ghost Reserve identity, neutral evidence surfaces and a separately styled dark map. Product structure carries authority: units, provenance, time boundaries, constraints and review states.

**Evidence standard:** “documented” means a published specification; “CSS sample” means values found on the linked public page or stylesheet during this review. Public websites, brand guidelines and annual reports are not evidence of a company's internal operational dashboard. Where a private product font or exact color could not be verified, it is explicitly marked unverified. No unofficial brand-color directories were used.

| Reference | Palette and typography evidence | Geography / uncertainty or risk | Density pattern and lesson |
| --- | --- | --- | --- |
| [USGS Mineral Resources](https://www.usgs.gov/tools/mineral-resources-online-spatial-data-access-tool) and [VIS](https://www.usgs.gov/information-policies-and-instructions/usgs-visual-identity-system) | VIS permits identifier green PMS348, black #000000 and white #FFFFFF. A web hex conversion for PMS348 and dashboard font were not independently verified. | Spatial datasets with metadata. [MRDS explicitly describes outdated operating-status and reserve information](https://energy.usgs.gov/arcgis/rest/services/Hosted/Mineral_Resource_Data_System/FeatureServer/0); a mine point is not a current reserve claim. | Use a queryable evidence register and dates. Carry data limitations into the inspection workflow, not only a help page. |
| [MoSPI eSankhyiki](https://esankhyiki.mospi.gov.in/) | [CSS sample](https://esankhyiki.mospi.gov.in/static/css/main.3fafb204.css): navy #0A266C, ink #3B4151, white #FFFFFF; Archivo declarations. Not a universal Indian-government palette. | Indicator/theme/catalogue navigation and trend views. No common numerical uncertainty treatment established by this review. | Overview leads into structured datasets. KPI context matters more than visual spectacle. |
| [IMD Mausam](https://mausam.imd.gov.in/) | [CSS sample](https://mausam.imd.gov.in/responsive/css/style.css): #004E99, #202124, #FFFFFF; Open Sans. | District forecast maps; [warning examples](https://mausam.imd.gov.in/Forecast/mcmarq/mcmarq_data/Press%20release%20No.4%20dated%2027%20Sept%202025%20on%20Increase%20in%20rainfall%20activity%20over%20Maharashtra.pdf) pair severity with Watch/Alert/Warning and action language. Warning levels are not confidence intervals. | Region, valid day and action must be visible together. Borrow the explicit labels, not an unexplained traffic-light gauge. |
| [Bhuvan](https://bhuvan.nrsc.gov.in/home/index.php) | Public-page CSS sample: #0B5EB7, #038EDC, #FFFFFF; repeated Roboto Condensed declarations. This samples the portal, not every embedded map application. | [Thematic services](https://bhuvan.nrsc.gov.in/wiki/index.php/Thematic_Data) expose layers via WMS. Layer presence does not establish uncertainty or regulatory clearance. | Keep a stable layer-control region beside the geography. Separate layer selection from selected-feature evidence. |
| [ArcGIS Calcite colors](https://developers.arcgis.com/calcite-design-system/foundations/colors/) and [typography](https://developers.arcgis.com/calcite-design-system/foundations/typography/) | Documented light tokens: #007AC2 brand, #F7F7F7/#FFFFFF/#F2F2F2 surfaces, #141414/#4A4A4A/#6B6B6B text. Avenir Next. | Distinct semantic statuses; quiet surfaces behind map imagery. Calcite status colors are not a statistical uncertainty model. | Borrow controlled surface hierarchy and sparse semantic color. Do not copy its blue brand merely because this is GIS. |
| [QGIS visual style](https://www.qgis.org/styleguide/) | Documented brand #589632/#93B023, accents #F0E64A/#EE7913; Trueno for brand communications. Desktop application typography varies by Qt/OS/theme. | Geological categories need legends; ordered quantities need ordered ramps. Desktop layer trees and attribute tables support inspection. | Borrow visible layers and inspectable attributes. QGIS's logo gradient is not a reason to add dashboard gradients. |
| [CARTOColors](https://carto.com/carto-colors/) | Page CSS sample #162945/#F2F6F9; published Burg ramp #FFC6C4 → #672044. An authenticated Builder font was not verified. | Documentation explicitly connects sequential lightness to quantitative order and advises reversing luminance for a dark basemap. Diverging scales are for deviations around a meaningful midpoint. | Use a fixed, labelled, monotonic score ramp. The workbench's brown ramp is our design, not a claimed CARTO preset. |
| [BHP operational review, FY2025](https://www.bhp.com/-/media/documents/media/reports-and-presentations/2025/250718_bhpoperationalreviewfortheyearended30june2025.pdf) | Exact production-document palette and font could not be independently extracted; do not invent hex values. Public report, not internal telemetry. | Production tables separate quarter/year, percentage changes, tonnes/kt/Mt and guidance ranges; footnotes qualify preliminary information. No geospatial interactive workflow in the reviewed report. | Borrow unit discipline, guidance ranges and compact comparisons. Guidance is not a statistical prediction interval. |
| [Rio Tinto reports](https://www.riotinto.com/en/invest/reports) and [KPIs](https://www.riotinto.com/en/invest/reports/annual-report/key-performance-indicators) | Exact report tokens/font were not independently verified. Branding must not be presented as evidence of its internal dashboard palette. | Separate operations/performance, resources/reserves, governance and sustainability disclosures. Financial/operational risk is contextual, not one universal score. | Keep output, forecast risk, material inventory and approval state separate. |
| [Vedanta FY25 interactive report](https://www.vedantalimited.com/vedantaFY25/) | [CSS sample](https://www.vedantalimited.com/vedantaFY25/css/style.css): #0067AC/#0064B0 blue, #6CC247/#72BF44 green; Roboto regular/medium/bold, some display-face declarations. | Multi-business and sustainability reporting; [TNFD report](https://www.vedantalimited.com/uploads/investor-overview/annual-report/2025/6_TNFD_Report_2025.pdf) reports nature-related assessment context. Not evidence of automated environmental approval. | Borrow substantive operational groupings and footnotes. Avoid annual-report decorative treatments in daily tools. |
| [Bloomberg Launchpad overview](https://www.bloomberg.com/professional/insights/technology/bloomberg-terminal-essentials-ib-worksheets-launchpad/) | Proprietary terminal hex values/font unverified. | Configurable analytical workspace. | Borrow compact linked panels. Do not imitate private terminal colors without evidence. |
| [Palantir Workshop](https://www.palantir.com/docs/foundry/workshop/concepts-widgets) | Public docs CSS sample #1E2124, #F4F7F6, #FFFFFF; Alliance No.2/No.1 stack. These are docs tokens, not a claim about every Foundry application. | [Chart widgets](https://www.palantir.com/docs/foundry/workshop/widgets-chart/index.html) support multiple series and linked selections; [time-series options](https://www.palantir.com/docs/foundry/workshop/widget-time-series-analysis) include line styles, point shapes and bands. | Borrow shared selection → object table → evidence → action, with stable side panels. |
| [NIC/MeitY GIGW](https://guidelines.india.gov.in/) and [DBIM v3](https://dbimtoolkit.digifootprint.gov.in/static/uploads/2025/01/b70a5719408bd6d60040eda3ac042053.pdf) | DBIM functional palette includes #FFFFFF, #EBEAEA, #150202; semantic #198754/#FFC107/#DC3545/#0D6EFD. [Noto Sans is specified](https://dbimtoolkit.digifootprint.gov.in/dbim-chapters?slug=typography). | Accessibility and textual meaning govern the interface; they do not prescribe a mineral score model. | Use multilingual-ready typography, explicit labels, right-aligned quantities and accessible markup. This prototype adapts those principles; it is not certified or an official ministry site. |

The reference systems are not uniformly austere. Several use gradients and bright colors. Rejecting those treatments here is a decision for this tool and its projector environment, not a claim that the references never use them.

## 2. Rejected patterns

- **Green as both brand and success.** In the old UI, an active filter, geographic inclusion and a promising score could appear to mean the same thing. Graphite means interaction; green now means a specific passed check.
- **Glass and translucent callouts.** Satellite imagery makes contrast unpredictable. Labels use opaque surfaces; no backdrop blur.
- **Decorative gradients, radar circles, neon, sci-fi grids.** These implied measurement without data. The missing-map fallback is a labelled coordinate plot. Its coordinate grid is functional, not decorative terrain.
- **Rounded marketing cards.** Components use 2/4/6/8px radii. Circular map markers encode geometry; they are not panel styling.
- **Generic #007AFF primary.** Selection and controls use graphite. Information links retain a restrained blue because the role is functional.
- **Rainbow prospectivity.** Hue changes do not imply a geological category when the data is a scalar score.
- **Large empty hero metrics.** One compact summary strip leads to a forecast, a screening register and a review queue.
- **Probability theatre.** A score of 0.84 is not displayed as “84% recoverable manganese.” A risk percentage is accompanied by its precise event, issue date and calibration status.

## 3. Proposed design system

### Scene and strategy

A MOIL analyst reads this tool in a bright office; SIH judges see it projected at 1920×1080. Use light neutral surfaces for text and numbers, an opaque dark geography canvas, and restrained colored marks. Avoid decorative motion; use 180ms feedback transitions and respect reduced motion.

### Palette and why each role exists

| Role | Hex | Reason, inspiration and task |
| --- | --- | --- |
| Primary graphite | #29343B; hover #182229; on-primary #FFFFFF | A strong, neutral control color does not masquerade as an ore score or success. Applies Calcite's separation of chrome and data. |
| Oxide accent | #874B2D; soft #F4EBE4 | A restrained earth reference for Ghost Reserve identity, not a mineral classifier. Works on white; does not compete with safety states. |
| Passed / success | #276348; soft #E8F1EB | Named checks only, paired with “Passed” or a check icon. Semantic distinction inspired by Calcite/IMD; not a blanket mining-safe label. |
| Review / warning | #805610; soft #FBF1D9 | Dark amber text remains readable on a projector. Review is a workflow state; a selected Ghost feature is never amber merely because it is selected. |
| Critical / error | #A12B32; soft #F9ECEC | Reserved for failure or an explicitly defined risk band, paired with text. Deep enough for ordinary-size labels. |
| Information / focus | #245C7D; soft #E9F0F5 | Distinguishes explanatory links and focus from the oxide domain marker; ordinary enterprise affordances. |
| Page / sidebar / panel | #F5F6F7 / #ECEFF1 / #FFFFFF | Three quiet levels make work regions readable without shadows. White is DBIM's functional baseline; neutral hierarchy follows Calcite. |
| Main text / secondary / metadata | #20262D / #52606A / #59636D | Contrast carries hierarchy without washed-out gray. Primary on page: 14.10:1. Metadata on sidebar: 5.30:1. |
| Divider / control border | #CBD1D6 / #7B8791 | Dividers group content; control boundaries must be stronger. Input border on white: 3.67:1. |
| Map / map text / map metadata | #172026 / #F4F6F7 / #B9C4CC | Stable contrast around satellite data. Text ratios on canvas: 15.24:1 and 9.31:1. |
| Map waste / exclusion / outside scope | #D9AB7C / #B9C4CC / #697680 | Waste is a diamond; exclusion is diagonal hatching; outside scope is neutral and explicitly unassessed. Three distinct concepts. |
| Map selection | #FFFFFF ring on #172026 backing | Two-tone contrast works across varied basemaps. List selection and named inspector provide a non-color equivalent. |

**Contrast interpretation:** WCAG 2.1 AA normally requires 4.5:1 for normal text. The requested 7:1 primary-text target is an enhanced contrast target, not the AA definition. Primary text exceeds it; secondary text remains ≥4.5:1 on its designated surfaces. Color checks alone do not establish whole-product WCAG or GIGW conformance. [W3C contrast guidance](https://www.w3.org/WAI/WCAG21/Understanding/contrast-enhanced.html).

Measured pairs: primary text/white 15.26:1; primary/page 14.10:1; primary/sidebar 13.21:1; secondary/white 6.48:1; metadata/sidebar 5.30:1; white/primary 12.74:1; oxide/oxide-soft 5.81:1; warning/warning-soft 5.74:1; success/success-soft 6.14:1; critical/critical-soft 6.27:1; info/info-soft 6.29:1. Satellite overlays still require basemap-specific review.

### Geography

| Score | Dark-map ramp | Relative luminance |
| --- | --- | --- |
| 0.00 | #49392A | 0.045 |
| 0.25 | #765638 | 0.108 |
| 0.50 | #A87946 | 0.224 |
| 0.75 | #D7AD6C | 0.454 |
| 0.99 | #F2DDA7 | 0.734 |

This is a sequential, luminance-monotonic ramp, not a claimed perceptually uniform scientific colormap. Label both endpoints and the active score field. On the dark canvas higher values are lighter. Keep the domain fixed at 0–0.99 when filtering; never rescale each viewport to manufacture contrast.

- Mask exclusion: 2px gray diagonals at an 8px repeat, backed by “Excluded by mask” and a reason. Do not paint exclusions as low prospectivity. Geological/occurrence masks are not ecological clearances.
- Ghost Reserve: copper-filled diamond, text “Waste/slag,” shared predicate waste-or-slag ∩ 5km-buffer membership ∩ geographic scope. Regular diagnostics remain circles.
- Selection: white ring, dark backing and name; preserve camera context during mask changes.
- Outside scope: muted geometry only if a verified coverage geometry is supplied, dashed boundary and “Outside validated scope (Sausar Belt).” Null scores, never zero.
- Missing data/unknown scope: “Unassessed,” no score fill, different from an exclusion.
- Printing: this implementation prints evidence tables and omits the WebGL basemap. A future geospatial print export should use a light basemap with the luminance order reversed (0: #F2DDA7 → 0.99: #49392A), retain hatching and numeric legend, and include north arrow/scale/CRS/attribution. Browser printing alone is not a validated cartographic export.

### Charts

- Actual series: #29343B, solid 2.5px line, circular points.
- Forecast: #874B2D, 6/4 dash, outlined points, explicit forecast-start month.
- Prediction interval: opaque #DDE5EB with #7B8791 boundary, independently labelled coverage and kind. Do not call a prediction interval a confidence interval.
- Risk: #276348 / #805610 / #A12B32 plus Low / Review / Critical and numerical probability. Demo display bands <30%, 30–<60%, ≥60% are illustrative, not validated policy.
- SHAP: + #245C7D, − #874B2D, zero reference, signed values and numeric table. Explain the underlying classifier output before PU adjustment/masks.
- Grayscale: line dashes, point outlines, signed numbers, band outlines, named states and tables preserve meaning.
- One-month horizon still displays an interval at that point; no continuity is fabricated across unavailable observations.

### Typography, spacing and geometry

Self-host Noto Sans through Fontsource; the browser fetches bundled WOFF2 from the app, not Google at runtime. Installed variable package supports available script subsets; actual Hindi localization still needs matching Noto Sans Devanagari assets and translated content. Do not imply that the English UI is already multilingual.

- Page heading: 28px/36px, 600. Panel/inspector title: 20–24px, 600. Section: 16px/24px, 600.
- Body/control: 14px/22px; explanations may use 14px/24px. Metadata: 12px/18px minimum.
- Scores: 34px, 600; risk probability: 36px. Data uses lining tabular numerals globally.
- This is a workstation-density adaptation, not a claim to reproduce DBIM's website type scale exactly.
- 4/8/12/16/24/32/48px spacing. 24px panel gaps; 16–20px internal padding. 40px buttons.
- 224px navigation, minimum 64px topbar, 368px inspector. Collapse navigation below 1440px; stack evidence below 1100px. Internal tables scroll rather than shrinking text.
- Cards 6px, controls 4px, small elements 2px; absolute panel maximum 8px. No large shadows, glass or decorative animation.

### Component treatment

**GhostReserveToggle:** inactive white, neutral border, oxide diamond; active oxide tint and oxide switch. On/Off text and Radix switch semantics. Asset eligibility is independent of whether screening masks are visually toggled.

**MaskToggleGroup:** one labelled fieldset with two named controls, Geological and 5km buffer. Graphite indicates enabled, not passed. Individual outcomes belong in Constraints.

**Scores:** adjacent numbers with stable labels. Raw remains visible; Screened gets a stronger baseline. A policy exclusion is explicitly labelled; an unknown/out-of-scope response suppresses numbers. No gauge around a prospectivity score.

**RiskGauge:** compact linear meter rather than a large speedometer. Probability, event month, threshold definition and unvalidated status are inspectable. A score payload renders in its original range and is not silently converted to a probability.

**ForecastRiskPanel:** large evidence plot left, risk evidence right. Horizon selection changes forecast points, not the risk's event month. An incompatible forecast ID prevents a combined interpretation. No forecast is synthesized by the UI.

**Inspector:** stable Evidence / Why? / Constraints tabs, opaque white surface, 1px separator; coordinates, score comparison and explanation above tabs; provenance below. All tabs retain keyboard behavior.

## 4. Implementation code

The implementation is in the existing Next.js 14 application. These are working files, not a replacement technology stack. CSS custom properties contain complete sRGB colors; Tailwind consumes var(--token) directly. Do not wrap these tokens in hsl(), which would break this shadcn configuration.


### CSS custom properties — app/globals.css

```css
:root {
  --background: #F5F6F7;
  --foreground: #20262D;
  --surface: #FFFFFF;
  --surface-raised: #ECEFF1;
  --sidebar: #ECEFF1;
  --card: #FFFFFF;
  --card-foreground: #20262D;
  --popover: #FFFFFF;
  --popover-foreground: #20262D;
  --primary: #29343B;
  --primary-hover: #182229;
  --primary-foreground: #FFFFFF;
  --primary-soft: #E3E8EB;
  --secondary: #E3E8EB;
  --secondary-foreground: #29343B;
  --accent: #E3E8EB;
  --accent-foreground: #29343B;
  --oxide: #874B2D;
  --oxide-soft: #F4EBE4;
  --success: #276348;
  --success-soft: #E8F1EB;
  --warning: #805610;
  --warning-soft: #FBF1D9;
  --critical: #A12B32;
  --critical-soft: #F9ECEC;
  --info: #245C7D;
  --info-soft: #E9F0F5;
  --destructive: #A12B32;
  --destructive-foreground: #FFFFFF;
  --muted: #ECEFF1;
  --muted-foreground: #52606A;
  --metadata: #59636D;
  --border: #CBD1D6;
  --input: #7B8791;
  --ring: #245C7D;
  --canvas: #172026;
  --canvas-ink: #F4F6F7;
  --canvas-muted: #B9C4CC;
  --map-low: #49392A;
  --map-quarter: #765638;
  --map-mid: #A87946;
  --map-three-quarter: #D7AD6C;
  --map-high: #F2DDA7;
  --map-ghost: #D9AB7C;
  --map-excluded: #B9C4CC;
  --map-selection: #FFFFFF;
  --map-out-of-scope: #697680;
  --chart-actual: #29343B;
  --chart-forecast: #874B2D;
  --chart-interval: #DDE5EB;
  --chart-positive: #245C7D;
  --chart-negative: #874B2D;
  --radius: 0.375rem;
  --space-1: 4px;
  --space-2: 8px;
  --space-3: 12px;
  --space-4: 16px;
  --space-6: 24px;
  --space-8: 32px;
  --space-12: 48px;
  --z-map: 0;
  --z-map-overlay: 10;
  --z-dropdown: 20;
  --z-sticky: 30;
  --z-modal: 40;
  --z-toast: 50;
  --font-sans: "Noto Sans Variable", "Noto Sans", Arial, sans-serif;
}
```


### Tailwind extension — tailwind.config.ts

```ts
import type { Config } from "tailwindcss";

export default {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        background: "var(--background)", foreground: "var(--foreground)",
        muted: "var(--muted)", "muted-foreground": "var(--muted-foreground)",
        border: "var(--border)", primary: "var(--primary)",
        "primary-foreground": "var(--primary-foreground)",
        card: "var(--card)", "card-foreground": "var(--card-foreground)",
        popover: "var(--popover)", "popover-foreground": "var(--popover-foreground)",
        secondary: "var(--secondary)", "secondary-foreground": "var(--secondary-foreground)",
        accent: "var(--accent)", "accent-foreground": "var(--accent-foreground)",
        destructive: "var(--destructive)", "destructive-foreground": "var(--destructive-foreground)",
        input: "var(--input)", ring: "var(--ring)",
        surface: "var(--surface)", sidebar: "var(--sidebar)",
        oxide: "var(--oxide)", "oxide-soft": "var(--oxide-soft)",
        success: "var(--success)", "success-soft": "var(--success-soft)",
        warning: "var(--warning)", "warning-soft": "var(--warning-soft)",
        critical: "var(--critical)", "critical-soft": "var(--critical-soft)",
        info: "var(--info)", "info-soft": "var(--info-soft)", metadata: "var(--metadata)",
      },
      fontFamily: { sans: ["Noto Sans Variable", "Noto Sans", "Arial", "sans-serif"] },
      fontSize: { metadata: ["0.75rem", "1.125rem"], body: ["0.875rem", "1.375rem"], section: ["1rem", "1.5rem"], heading: ["1.5rem", "2rem"] },
      spacing: { gutter: "var(--space-6)", section: "var(--space-8)", rail: "224px", inspector: "368px" },
      borderRadius: { sm: "2px", md: "4px", lg: "6px", xl: "8px" },
      transitionDuration: { DEFAULT: "180ms" },
    },
  },
  plugins: [],
} satisfies Config;
```


### shadcn/Radix button override — components/ui/button.tsx

```tsx
import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import { cva, type VariantProps } from "class-variance-authority";
import { cn } from "@/lib/utils";

const variants = cva("inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-md text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50", {
  variants: { variant: { default: "bg-primary text-primary-foreground hover:bg-[var(--primary-hover)]", outline: "border border-input bg-surface hover:bg-muted", ghost: "text-muted-foreground hover:bg-muted hover:text-foreground" }, size: { default: "h-10 px-4", sm: "h-9 px-3", icon: "h-10 w-10" } },
  defaultVariants: { variant: "default", size: "default" },
});
export interface ButtonProps extends React.ButtonHTMLAttributes<HTMLButtonElement>, VariantProps<typeof variants> { asChild?: boolean }
export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(({ className, variant, size, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button";
  return <Comp className={cn(variants({ variant, size }), className)} ref={ref} {...props} />;
});
Button.displayName = "Button";
```

Switch and Tabs retain Radix semantics. Their matching overrides live in [switch.tsx](../components/ui/switch.tsx) and [tabs.tsx](../components/ui/tabs.tsx). Switch state uses graphite by default and oxide only for the Ghost toggle. Outline controls use the stronger input border; focus uses the information-color ring. Selected tabs also differ by surface and label weight.


### Mapbox GL layer JSON — public/styles/prospectivity.layers.json

```json
[
  {
    "id": "prospectivity-screened",
    "type": "fill",
    "source": "prediction-cells",
    "source-layer": "prediction_cells",
    "filter": [
      "all",
      ["==", ["get", "scope_status"], "in_scope"],
      ["==", ["get", "mask_excluded"], false],
      ["==", ["typeof", ["get", "final_score"]], "number"],
      [">=", ["get", "final_score"], 0],
      ["<=", ["get", "final_score"], 0.99]
    ],
    "paint": {
      "fill-color": [
        "interpolate", ["linear"], ["get", "final_score"],
        0, "#49392A",
        0.25, "#765638",
        0.5, "#A87946",
        0.75, "#D7AD6C",
        0.99, "#F2DDA7"
      ],
      "fill-opacity": 0.82
    }
  },
  {
    "id": "prospectivity-excluded",
    "type": "fill",
    "source": "prediction-cells",
    "source-layer": "prediction_cells",
    "filter": ["all", ["==", ["get", "scope_status"], "in_scope"], ["==", ["get", "mask_excluded"], true]],
    "paint": { "fill-pattern": "excluded-hatch", "fill-opacity": 1 }
  },
  {
    "id": "prospectivity-outside-scope",
    "type": "fill",
    "source": "prediction-cells",
    "source-layer": "prediction_cells",
    "filter": ["==", ["get", "scope_status"], "out_of_scope"],
    "paint": { "fill-color": "#697680", "fill-opacity": 0.28 }
  }
]
```

**Integration contract:** this is an array of layers, not a complete style or an existing endpoint. It requires a vector source named `prediction-cells` and a `prediction_cells` source-layer with numeric `final_score`, boolean `mask_excluded` and `scope_status`. The adapter derives `mask_excluded` from actual mask outcomes; `mask_applied` alone only identifies enabled policies. Register the hatch image on every `style.load` before adding the layers. Keep waste diamonds and selection layers above the surface. Unknown scope and absent scores are not filled. This snippet is supplied for backend integration and is not connected to fixture geography.

For multi-million-pixel production rasters, use backend-windowed COG processing and tiled raster rendering with the same numerical ramp/NoData mask; do not generate one browser polygon per pixel. A Mapbox `heatmap` layer shows point density and must not be passed off as the model's per-pixel prospectivity. Do not apply a GeoJSON `get` expression to an ordinary RGB raster. [Mapbox style reference](https://docs.mapbox.com/style-spec/reference/layers/).


### Mask pattern registration — lib/map/register-mask-pattern.ts

```ts
import type { Map } from "mapbox-gl";

/** Semantic map exclusion pattern. Re-register on style.load, before addLayer.
 * 8×8 power-of-two sprite: two gray pixels / six transparent pixels per diagonal.
 * Never apply this pattern to unknown scope or use it as UI decoration. */
export function registerMaskPattern(map: Map): void {
  if (map.hasImage("excluded-hatch")) return;
  const width = 8;
  const data = new Uint8Array(width * width * 4);
  for (let y = 0; y < width; y++) {
    for (let x = 0; x < width; x++) {
      const offset = (y * width + x) * 4;
      data[offset] = 185; data[offset + 1] = 196; data[offset + 2] = 204;
      data[offset + 3] = (x + y) % 8 < 2 ? 255 : 0;
    }
  }
  map.addImage("excluded-hatch", { width, height: width, data }, { pixelRatio: 1 });
}
```


### Complex component — components/operations/forecast-risk-panel.tsx

```tsx
"use client";

import { useState } from "react";
import type { ForecastResponse, RiskResponse } from "@/lib/contracts";
import { ProductionChart, tonnes, type HistoricalPoint } from "./production-chart";
import { RiskGauge } from "./risk-gauge";
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs";

/** Full-system example: typed evidence, query horizon, uncertainty, accessible table,
 * neutral surfaces, semantic states, and a related risk which keeps its own horizon. */
export function ForecastRiskPanel({ forecast, risk, history }: {
  forecast: ForecastResponse; risk: RiskResponse; history: readonly HistoricalPoint[];
}) {
  const [horizon, setHorizon] = useState("3");
  const first = forecast.points[0];
  const displayedForecast = horizon === "1" ? { ...forecast, horizon_months: 1 as const, points: forecast.points.slice(0, 1) } : forecast;
  const issueDate = new Date(forecast.issue_date).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric", timeZone: "UTC" });
  return <div className="briefing-columns">
    <section className="print-section min-w-0 rounded-lg border bg-surface" aria-labelledby="forecast-heading">
      <div className="flex flex-wrap items-start justify-between gap-3 px-5 pt-5">
        <div><h2 id="forecast-heading" className="section-heading">Production outlook</h2><p className="mt-1 text-xs text-metadata">MOIL company-wide · tonnes · issued {issueDate}</p></div>
        <Tabs value={horizon} onValueChange={setHorizon} className="no-print"><TabsList aria-label="Forecast horizon"><TabsTrigger value="1">1 month</TabsTrigger><TabsTrigger value="3">3 months</TabsTrigger></TabsList></Tabs>
      </div>
      <div className="mx-5 my-3 flex flex-wrap items-center gap-x-5 gap-y-2 border-b pb-3 text-sm">
        <span>Next month <strong className="ml-1 font-semibold">{first ? tonnes(first.point_estimate) : "Unavailable"} t</strong></span>
        <span className="text-muted-foreground">{first?.lower_bound !== null && first?.upper_bound !== null && first ? `${tonnes(first.lower_bound)}–${tonnes(first.upper_bound)} t` : "Bounds unavailable"}</span>
      </div>
      <div className="px-4 pb-4"><ProductionChart forecast={displayedForecast} history={history} /></div>
      <p className="border-t px-5 py-3 text-xs leading-5 text-metadata">{forecast.provenance.data_origin === "fixture" ? "All plotted values, including the actual-series example, are synthetic. Interval coverage has not been validated." : forecast.provenance.source}</p>
    </section>
    <aside className="rounded-lg border bg-surface p-5">
      {risk.reference_forecast_id === forecast.forecast_id ? <RiskGauge risk={risk} /> : <p role="alert">Risk references a different forecast. A combined interpretation is unavailable.</p>}
    </aside>
  </div>;
}
```

The complex component composes [ProductionChart](../components/operations/production-chart.tsx) and [RiskGauge](../components/operations/risk-gauge.tsx). Its concrete fixture usage is in [Command Center](../app/(workspace)/page.tsx). The implementation's one-/three-month selector is scoped to the supplied three-month demo contract; a live service with other horizons must expose only the returned horizons.

Installations: pinned `@fontsource-variable/noto-sans@5.3.0`; root layout imports its package stylesheet. No runtime third-party font request. Rendering uses the existing Recharts, Mapbox GL, Radix, Zustand and Lucide stack.

## 5. Visual description of the transformed UI

At 1920×1080, a 224px gray navigation rail anchors the left edge. A small graphite square and a plain two-line product name establish identity without an emblem or invented official seal. The active navigation item is a solid graphite rectangle; other items are quiet. Scope and prototype identity sit below the navigation.

The white topbar contains a breadcrumb and a compact “Demo data” badge. The Command Center opens with **Operational briefing**, a one-line explanation and a Print briefing control. There is no greeting, marketing headline or animated counter.

A single horizontal summary strip lists screening locations, Ghost candidates and proposed reviews. Reported prospectivity LOBO AUC is explicitly labelled as prospectivity evidence, not forecast validation.

The main column gives roughly three quarters of the work area to a production plot. Values use Indian digit grouping and explicit tonnes. A solid graphite historical series ends before a dashed oxide forecast. The bounded gray interval has its coverage label and a visible forecast-start month. Every value is inspectable in a table. The fixture disclaimer remains immediately under the chart.

A 340px right column presents the risk event and its probability. The horizontal scale occupies little height, leaving room for the plain-English event definition. Definition, demo thresholds and model limitations expand inline.

Below, a screening register lists names, raw scores, buffer membership and the next missing evidence. Waste diamonds distinguish material candidates from the circular farmland diagnostic. Adjacent to it, the review queue shows rule ID, status, recommendation and triggering evidence. This is substantial because it answers real questions, not because panels were filled with decorative charts.

The Explorer uses the same shell with a dark, opaque map and a 368px inspector. Ghost mode is the sole oxide control. Raw and screened evidence remain visible above the tabs. The missing-token state shows a coordinate plot with named demonstration sites and a truthful unavailable-surface label; it does not generate pretend satellite imagery.

On compact screens the rail collapses and panels stack. At desktop heights some lower explanatory content may require vertical scrolling; numbers and controls do not shrink to fit. For a projector, keep browser zoom at 100% and demonstrate one question at a time.

Print briefing expands evidence details, removes navigation/map canvas, switches semantic tokens to grayscale and retains dashed forecast lines, signed SHAP values and labelled states. Numeric tables are the authoritative black-and-white fallback; a georeferenced printable map is separate future export work.

## 6. Three before/after comparisons

| Before | After | What improves |
| --- | --- | --- |
| Green navigation, green Ghost toggle, green score tint and a similarly colored geographic-status badge | Graphite interaction, oxide waste identity, separately labelled passed/review states; raw/screened numeric comparison | Color no longer conflates being selected, being in scope and being environmentally safe. |
| Empty “One workbench. Four decisions.” roadmap landing page | Forecast with bounds, defined risk, four-location screening register and linked rule evidence | Officials can follow supply outlook → candidate evidence → review in one workspace. Simulated evidence is labelled. |
| Frosted missing-map card, radial terrain wash and decorative circles | Opaque coordinate plot, diamond/circle categories, readable selection label and explicit unavailable-map status | The fallback remains useful without visually implying satellite or coverage data that has not loaded. |

### Verification and remaining integration limits

- TypeScript check passed; 11 existing contract tests passed.
- Both Playwright workflows passed: masks/Ghost/scope/SHAP and briefing/horizon/linked-risk/provenance/navigation.
- Browser screenshots checked at 1920×1080, Explorer at 1366×768, and Command Center at 390px; monochrome print styling reviewed. A full accessibility certification was not performed.
- Production build passed with all four routes generated.
- Live satellite tiles need a public Mapbox token. Live prospectivity tiles, verified inventory/assays, forecasts and approval persistence are not connected; the UI does not claim otherwise.
- npm audit reports a high-severity finding on the existing pinned Next.js 14 dependency. This redesign preserves the explicitly requested major version; a maintained-version migration is required before calling the application deployment-ready.
