# Phase 7 — Report generation and export center

Implemented `/reports` with a local workflow:

- `ReportTemplateSelector.tsx` provides three selectable report templates with accessible pressed state and copper selection treatment.
- `ReportConfigurationForm.tsx` provides date range, native multi-select mine targeting and PDF/Excel/CSV radio choices. Generation simulates a short loading state and reports local-only completion.
- `RecentReportsTable.tsx` provides four illustrative export rows plus disabled download controls until a document service exists.
- `ReportsCenter.tsx` owns template selection and session-only report rows.

No download endpoint, export API, file generation or new contract was invented. New records are marked Local only and disappear on reload. The page retains evidence caveats and states that generated exports do not certify their source data.

Verification: TypeScript, production build and 15 unit tests passed. Browser checks confirmed template selection, output-format selection, simulated generation (4 rows to 5), confirmation messaging, disabled download actions and 390px no-overflow behavior. Existing pages, API clients and contracts were not modified.

Screenshots: `output/playwright/phase7/reports-desktop.png` and `reports-mobile.png`.
