# Phase 5 — Asset and inventory management

Implemented `/assets` with three modular operational surfaces:

- `MineOverviewGrid.tsx` shows six illustrative mine cards with operational status, monthly output and equipment count.
- `GhostReserveInventory.tsx` highlights three synthetic waste/slag records and keeps raw score, screened score, volume and assay status separate. Missing screening remains an em dash.
- `EquipmentFleetStatus.tsx` shows five illustrative fleet records with assignment, state and planned maintenance date.

The Ghost Reserve register is visually prioritized with copper title, border and selected-row treatment. Its disclaimer explicitly states that screening indices are not measured ore, reserve tonnage or environmental approval. No operational action, reservation, assay claim or backend endpoint was added.

Verification: TypeScript, production build and 15 unit tests passed. The page was checked at 1920×1080 and 390×844; the tables remain contained in their keyboard-accessible horizontal regions and the mobile document has no viewport overflow. Existing pages, API clients and contracts were not modified.

Screenshots: `output/playwright/phase5/assets-desktop.png` and `assets-mobile.png`.
