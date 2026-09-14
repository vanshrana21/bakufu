import type { Annotation } from "./types";

/** Explicitly synthetic examples, never merged with backend data. */
export const demoAnnotations: readonly Annotation[] = [
  { id: "DEMO-004", createdAt: "2026-09-12T08:30:00Z", siteId: "demo-dump-a", siteName: "Demo waste dump A", type: "False Positive", severity: "High", notes: "Illustrative geologist concern: surface material may not represent recoverable manganese. Assay evidence is required.", status: "Pending", source: "example" },
  { id: "DEMO-003", createdAt: "2026-09-11T10:15:00Z", siteId: "demo-slag-b", siteName: "Demo slag heap B", type: "Data Quality Issue", severity: "Medium", notes: "Illustrative request to review acquisition quality and processing provenance before interpreting this material.", status: "Pending", source: "example" },
  { id: "DEMO-002", createdAt: "2026-09-10T09:00:00Z", siteId: "demo-dump-c", siteName: "Demo waste dump C", type: "False Negative", severity: "High", notes: "Illustrative missed-target report. Check whether screening masks, rather than raw model output, caused exclusion.", status: "Reviewed", source: "example" },
  { id: "DEMO-001", createdAt: "2026-09-09T07:45:00Z", siteId: "demo-dump-a", siteName: "Demo waste dump A", type: "Data Quality Issue", severity: "Low", notes: "Illustrative metadata review. A reviewed annotation is not a verified assay or approval for model training.", status: "Reviewed", source: "example" },
];
