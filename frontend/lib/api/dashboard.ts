/** Adapter for GET /dashboard/summary -> the four VitalSigns tiles.
 *
 * This is the smallest live surface and the right first integration: one call,
 * it exercises CORS, and it carries `degraded[]` and `data_provenance` — the two
 * fields that tell the UI whether what it is about to render is trustworthy.
 */

import type { WireDashboardSummary } from "./wire";
import { apiGet } from "./client";
import { parseWire, WireDashboardSummarySchema } from "./wire-schemas";

export interface VitalSign {
  label: string;
  value: string;
  unit: string | null;
  note: string;
  testId?: string;
  /** True when the backing component failed to load. The tile renders an em
   * dash rather than a number: a missing value must never look like zero. */
  unavailable: boolean;
}

export interface DashboardResult {
  signs: VitalSign[];
  degraded: string[];
  /** Non-null only when the backend says the served artifacts are NOT the real
   * trained models. The UI must show this — it is the difference between a demo
   * and a claim. */
  syntheticNote: string | null;
  generatedAt: string;
  seriesHealth: WireDashboardSummary["series_health"];
  modelHealth: WireDashboardSummary["model_health"];
}

const tonnes = (value: number) => new Intl.NumberFormat("en-IN").format(Math.round(value));
const monthLabel = (month: string) =>
  new Date(`${month}-01T00:00:00Z`).toLocaleDateString("en-IN", { month: "long", year: "numeric", timeZone: "UTC" });

export function adaptDashboardSummary(wire: WireDashboardSummary, pendingReviews: number | null): DashboardResult {
  const degraded = wire.degraded ?? [];
  const latest = wire.latest_actual;
  const next = wire.next_forecast;
  const shortfall = wire.shortfall;

  const signs: VitalSign[] = [
    {
      label: "Latest production",
      value: latest ? tonnes(latest.mh_plus_mp_tonnes) : "—",
      unit: latest ? "t" : null,
      note: latest
        ? `${monthLabel(latest.month)} · MH+MP observed · ${tonnes(latest.all_india_tonnes)} t all-India`
        : "Production series unavailable",
      unavailable: !latest,
    },
    {
      label: "Next-month forecast",
      value: next ? tonnes(next.predicted_tonnes) : "—",
      unit: next ? "t" : null,
      // Bounds are formatted from the response, never hardcoded: the fixture
      // build had "80% bounds 108-142k t" baked into the string.
      note: next
        ? `${monthLabel(next.month)} · ${Math.round(next.ci_level * 100)}% bounds ${tonnes(next.lower_ci)}–${tonnes(next.upper_ci)} t`
        : "Forecast unavailable",
      unavailable: !next,
    },
    {
      label: "Downside risk",
      value: shortfall ? `${Math.round(shortfall.probability * 100)}%` : "—",
      unit: null,
      note: shortfall
        ? `${monthLabel(shortfall.month)} · below 90% of issued forecast · ${shortfall.risk_level} · screening only`
        : "Shortfall model unavailable",
      testId: "vital-risk",
      unavailable: !shortfall,
    },
    {
      label: "Pending reviews",
      value: pendingReviews === null ? "—" : String(pendingReviews).padStart(2, "0"),
      unit: pendingReviews === null ? null : "awaiting review",
      note: pendingReviews === null
        ? "Recommendations unavailable"
        : "Proposed actions · no approvals recorded",
      unavailable: pendingReviews === null,
    },
  ];

  const provenance = wire.data_provenance;
  return {
    signs,
    degraded,
    syntheticNote: provenance?.synthetic
      ? provenance.note ?? "The API is serving synthetic development artifacts, not the trained production models. Numbers are structurally valid but scientifically meaningless."
      : null,
    generatedAt: wire.generated_at,
    seriesHealth: wire.series_health,
    modelHealth: wire.model_health,
  };
}

export const fetchDashboardSummary = (pendingReviews: number | null, signal?: AbortSignal) =>
  apiGet<unknown>("/dashboard/summary", { signal })
    .then((raw) => parseWire(WireDashboardSummarySchema, raw, "/dashboard/summary"))
    .then((wire) => adaptDashboardSummary(wire, pendingReviews));
