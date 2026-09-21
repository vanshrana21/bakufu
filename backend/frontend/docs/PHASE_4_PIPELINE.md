# Phase 4 — Pipeline and model health

Implemented `/pipeline` with three modular surfaces:

- `components/pipeline/IngestionStatusGrid.tsx` presents STAC, BSE and IMD freshness with explicit Active/Warning states, sync timestamps and record counts.
- `components/pipeline/ModelVersionRegistry.tsx` presents four illustrative registry entries, monospaced version IDs and LOBO/MAPE metrics. Deployed rows use the existing selected-row copper tint; status badges remain semantic.
- `components/pipeline/RetrainingLog.tsx` presents the active-learning event trail and separates triggers, actions and outcomes.

The source records are synthetic UI metadata. The page says so, and it does not invent API endpoints, MLflow calls, retraining mutations or new contracts. “Deployed” is an illustrative registry state; it is not a certification of measured ore, model generalization beyond Sausar Belt or a completed backend operation.

Verification: TypeScript, production build, 15 unit tests and all six existing Playwright regression tests passed in Chrome. The new page was visually checked at 1920×1080 and 390×844; mobile width remains within the viewport and the model table scrolls within its accessible region. Existing four pages and all other route shells were not modified.
