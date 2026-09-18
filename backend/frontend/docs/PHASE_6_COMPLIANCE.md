# Phase 6 — Regulatory and compliance tracker

Implemented `/compliance` with three modular surfaces:

- `ComplianceOverviewGrid.tsx` summarizes active permits, renewals inside 90 days and open audit findings.
- `PermitRegistryTable.tsx` presents six illustrative clearances and permits with monospaced IDs, authorities, dates and semantic status badges. Expiring rows use the existing selected-row tint for review priority.
- `AuditLogTimeline.tsx` presents three recent inspection, submission and finding events in chronological order.

The page labels its records as illustrative planning metadata and states that authoritative MoEFCC, DGMS, MPCB, CGWA and IBM records remain the source of legal status. It does not grant clearance, certify compliance or create a workflow mutation.

Verification: TypeScript, production build and 15 unit tests passed. The page was visually checked at 1920×1080 and 390×844; permit rows remain inside the accessible table scroll region and the mobile document has no viewport overflow. Existing pages, API clients and contracts were not modified.

Screenshots: `output/playwright/phase6/compliance-desktop.png` and `compliance-mobile.png`.
