# Phase 1 — Mineral Intelligence Command Center

Status: design-system foundation implemented. Phase 2 routes/navigation and Phase 3 page integrations have not begun.

## Audit and decisions

- Existing styles already used copper but mixed hardcoded layout colors with semantic tokens. Preserve layout geometry and scientific encodings; establish reusable light/dark surface tokens first.
- Existing UI directory contained only Button, Switch and Tabs. Added Card, Table and Badge without migrating existing business components or changing their contracts.
- White reading surfaces on a cool neutral page. Explicit `data-theme="dark"` for future map/analytics containers; `data-theme="light"` restores a light report within them. No automatic OS-based theme changes. Apply these scopes to token-based surfaces, not indiscriminately to legacy layouts with fixed colors.
- Primary filled actions remain #C44016 in both themes. Separate primary-ink and ring tokens give links and focus indicators sufficient contrast on charcoal.
- Noto Sans Variable remains self-hosted. JetBrains Mono Variable is now actually bundled; `font-mono` resolves to it. All data retains tabular numerals.
- Compact 2/4/6/8px corner scale, 1px borders, no shadows on static cards, no new gradients or glass effects. Raised overlays alone have an optional shadow token.
- Map ramp, Ghost Reserve colors, mask meanings, score contracts and chart encodings remain unchanged. Semantic badges require explicit text; color alone does not establish scientific status.

## Component API

- Button preserves `asChild`, native events, type, refs, existing default/outline/ghost variants and default/sm/icon sizes. Adds secondary/destructive/link and lg. Native button submit behavior is unchanged. Callers must name icon-only controls; disable links through actual navigation logic, not just styling.
- Card, CardHeader, CardTitle (h2), CardDescription, CardContent, CardFooter: semantic text hierarchy and theme-aware container. The card itself is not an interactive control.
- Table, TableHeader, TableBody, TableFooter, TableRow, TableHead, TableCell, TableCaption: native table semantics and keyboard-scrollable overflow region. Provide a specific scrollLabel and caption. Use scope="row" for row headers; numeric cells use `text-right font-mono`. Selected rows accept data-state="selected"; selection logic belongs to the caller. A visual row hover does not make rows clickable.
- Badge variants: secondary (default), default (copper), outline, success, warning, destructive, info. A span with no forced live-region role. Success must never imply an assay or approval the backend has not supplied.

## Exact upgraded CSS variables and surface rules

This block is copied verbatim from app/globals.css. Existing layout rules follow it in the source file.

```css
:root, [data-theme="light"] {
  --grey-900: #0C0C0C;
  --grey-850: #141415;
  --grey-800: #18191B;
  --grey-750: #222326;
  --grey-700: #2F3032;
  --grey-600: #464749;
  --grey-500: #747576;
  --grey-400: #8B8C8D;
  --grey-300: #A3A3A4;
  --grey-200: #C3C4C8;
  --grey-150: #E0E1E3;
  --grey-100: #EFF0F1;
  --background: #F3F4F5;
  --foreground: #20262D;
  --surface: #FFFFFF;
  --surface-raised: #ECEEF0;
  --sidebar: #E7EAED;
  --card: #FFFFFF;
  --card-foreground: #20262D;
  --popover: #FFFFFF;
  --popover-foreground: #20272B;
  --primary: #C44016;
  --primary-hover: #A73210;
  --primary-foreground: #FFFFFF;
  --primary-soft: #FBECE6;
  --secondary: #E3E8E9;
  --secondary-foreground: #29343B;
  --accent: #E3E8E9;
  --accent-foreground: #29343B;
  --oxide: #236D64;
  --oxide-soft: #E6F0ED;
  --success: #226146;
  --success-soft: #E5F0E9;
  --warning: #80520D;
  --warning-soft: #FBF3DF;
  --critical: #AE323D;
  --critical-soft: #F9E9EB;
  --info: #245C78;
  --info-soft: #E5F0F5;
  --destructive: #AE323D;
  --destructive-foreground: #FFFFFF;
  --muted: #ECEEF0;
  --muted-foreground: #535D68;
  --metadata: #58616C;
  --border: #D4D8DD;
  --border-dark: #2F3032;
  --input: #7D8792;
  --ring: #C44016;
  --canvas: #171C22;
  --canvas-ink: #EFF0F1;
  --canvas-muted: #A3A3A4;
  --brand-orange: #FE5B2A;
  --brand-orange-400: #FE7C55;
  --brand-orange-600: #E75326;
  --map-low: #ADAEA2;
  --map-quarter: #E0C396;
  --map-mid: #F2B153;
  --map-three-quarter: #F48137;
  --map-high: #E45227;
  --map-ghost: #62C5B5;
  --map-excluded: #B9C4CC;
  --map-selection: #FFFFFF;
  --map-out-of-scope: #697680;
  --chart-actual: #33494D;
  --chart-forecast: #C44016;
  --chart-interval: #F4DCD0;
  --chart-positive: #236D64;
  --chart-negative: #C44016;
  --primary-active: #8F2B0C;
  --primary-ink: #A73210;
  --row-hover: #F3F4F5;
  --row-selected: #FBECE6;
  --border-strong: #7D8792;
  --shadow-popover: 0 8px 24px #171C2214;
  --radius: 0.25rem;
  --radius-sm: 0.125rem;
  --radius-lg: 0.375rem;
  --radius-xl: 0.5rem;
  color-scheme: light;
  --space-1: 4px; --space-2: 8px; --space-3: 12px; --space-4: 16px;
  --space-6: 24px; --space-8: 32px; --space-12: 48px;
  --z-map: 0; --z-map-overlay: 10; --z-dropdown: 20; --z-sticky: 30; --z-modal: 40; --z-toast: 50;
  --font-sans: "Noto Sans Variable", "Noto Sans", Arial, sans-serif;
  --font-mono: "JetBrains Mono Variable", "JetBrains Mono", "SF Mono", SFMono-Regular, Menlo, Consolas, monospace;
  /* One easing and two durations for the whole interface. Motion is either a
   * one-time reveal on enter or scrubbed to scroll — never looping or decorative. */
  --ease-out: cubic-bezier(.22,.61,.36,1);
  --dur-fast: 180ms;
  --dur-reveal: 420ms;
}
/* Opt-in surface scope. A light report can be nested inside a dark workspace.
 * This is deliberately not tied to OS preference: evidence stays in its chosen context.
 * Copper stays #C44016 on filled actions; a lighter ink is required on dark backgrounds. */
[data-theme="dark"] {
  color-scheme: dark;
  --background: #11161C;
  --foreground: #F0F2F4;
  --surface: #171C22;
  --surface-raised: #222931;
  --sidebar: #141A20;
  --card: #1B222A;
  --card-foreground: #F0F2F4;
  --popover: #222931;
  --popover-foreground: #F0F2F4;
  --primary: #C44016;
  --primary-hover: #A73210;
  --primary-active: #8F2B0C;
  --primary-foreground: #FFFFFF;
  --primary-ink: #FFAA8B;
  --primary-soft: #35241F;
  --secondary: #2B343E;
  --secondary-foreground: #E6EAEE;
  --accent: #2B343E;
  --accent-foreground: #E6EAEE;
  --muted: #252D36;
  --muted-foreground: #ADB7C2;
  --metadata: #ADB7C2;
  --border: #3B4653;
  --border-strong: #7D8A99;
  --input: #7D8A99;
  --ring: #FFAA8B;
  --row-hover: #252D36;
  --row-selected: #35241F;
  --oxide: #86D6C3;
  --oxide-soft: #183B33;
  --success: #9CDBB9;
  --success-soft: #173729;
  --warning: #F2CC86;
  --warning-soft: #3A301E;
  --critical: #FFB1B8;
  --critical-soft: #41232B;
  --info: #CDD3DA;
  --info-soft: #29313A;
  --destructive: #AE323D;
  --destructive-foreground: #FFFFFF;
  --shadow-popover: 0 8px 24px #00000040;
}
[data-theme] { background-color: var(--background); color: var(--foreground); }
/* Reusable primitives only; existing layouts keep their current geometry. */
.ui-control { outline-offset: 2px; }
.ui-control:focus-visible { outline: 2px solid var(--ring); }
.ui-control[aria-disabled="true"] { pointer-events: none; opacity: .5; }
.ui-table-scroll { scrollbar-width: thin; }
.ui-table-scroll:focus-visible { outline: 2px solid var(--ring); outline-offset: 2px; }
@media print {
  [data-theme="dark"] {
    color-scheme: light;
    --background: #FFFFFF; --foreground: #000000; --surface: #FFFFFF;
    --card: #FFFFFF; --card-foreground: #000000; --muted: #EEEEEE;
    --muted-foreground: #333333; --metadata: #333333; --border: #888888;
    --surface-raised: #EEEEEE; --row-hover: #FFFFFF; --row-selected: #EEEEEE;
    --primary-ink: #222222; --primary-soft: #EEEEEE;
    --success: #222222; --success-soft: #EEEEEE;
    --warning: #222222; --warning-soft: #EEEEEE;
    --critical: #222222; --critical-soft: #EEEEEE;
    --info: #222222; --info-soft: #EEEEEE;
  }
  .ui-table-scroll { overflow: visible; }
}
```

## Exact Tailwind configuration

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
        "primary-hover": "var(--primary-hover)", "primary-active": "var(--primary-active)",
        "primary-ink": "var(--primary-ink)", "primary-soft": "var(--primary-soft)",
        "surface-raised": "var(--surface-raised)", "border-strong": "var(--border-strong)",
        "row-hover": "var(--row-hover)", "row-selected": "var(--row-selected)",
        canvas: "var(--canvas)", "canvas-ink": "var(--canvas-ink)", "canvas-muted": "var(--canvas-muted)",
      },
      fontFamily: { sans: ["var(--font-sans)"], mono: ["var(--font-mono)"] },
      fontSize: { metadata: ["0.75rem", "1.125rem"], body: ["0.875rem", "1.375rem"], section: ["1rem", "1.5rem"], heading: ["1.5rem", "2rem"] },
      spacing: { gutter: "var(--space-6)", section: "var(--space-8)", rail: "224px", inspector: "368px" },
      borderRadius: { sm: "var(--radius-sm)", md: "var(--radius)", lg: "var(--radius-lg)", xl: "var(--radius-xl)" },
      boxShadow: { popover: "var(--shadow-popover)" },
      transitionDuration: { DEFAULT: "180ms" },
      transitionTimingFunction: { DEFAULT: "var(--ease-out)" },
    },
  },
  plugins: [],
} satisfies Config;
```

## Verification

- Production build: successful on an isolated repository copy; all original routes generated. No new routes.
- TypeScript: `npm run typecheck` passed.
- Unit tests: 15/15 passed, unchanged test files.
- Existing Playwright specs: 6/6 passed in installed Chrome at an isolated port. The default bundled Chromium executable is missing on this machine, so the supported PLAYWRIGHT_CHANNEL=chrome override was used.
- Regression scope: existing fixture mode, not live service validation. Existing fixture files were not modified and no business mock data was added. Mask independence, raw/screened values, out-of-scope handling, review navigation, printing and narrow-screen navigation passed.
- Color checks: 18 light/dark foreground/background pairs passed WCAG AA normal-text contrast; primary white-on-copper is 5.13:1. This is token contrast verification, not a complete application accessibility audit.
- SHA-256 comparison: all 10 files in lib/api/ plus lib/contracts.ts (10 total) are byte-for-byte unchanged.
- Screenshot evidence: output/playwright/phase1/. Actual primitive preview includes both themes; regression screenshots cover existing views.
- npm audit reports four existing-stack advisories (two critical: next and maplibre-gl; two moderate: vitest and @vitest/mocker). The only dependency added in this phase is the self-hosted font. Major-version dependency migration is outside this design phase.

## Deferred until approval

Six additional routes, grouped navigation, page composition, and backend endpoint wiring. Existing fixed layout colors and the Explorer's unused right-column space require composition work in later phases; token scaffolding alone does not constitute the complete visual redesign.
