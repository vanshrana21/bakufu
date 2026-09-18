# Phase 2 — Routing and shell

Six route placeholders added: /assets, /feedback, /pipeline, /compliance, /reports, /admin. Each has a page title, descriptive heading and an explicit integration-pending message. No mock records, endpoint assumptions or operational controls were added. The admin placeholder explicitly states that access controls are not implemented.

Navigation uses a 236px charcoal sidebar above 1100px, grouped into Operations, Intelligence and Administration. Below that width it becomes an inline menu disclosure with aria-expanded, keyboard access, Escape dismissal, focus return and automatic closure after navigation. Active links use aria-current and copper tokens. The header and sidebar remain accessible during desktop scrolling; print excludes navigation.

Shared placeholder: components/shell/module-placeholder.tsx. Shell styling is isolated in components/shell/app-shell.module.css. Existing global styles and Phase 1 tokens were not changed.

Verification: TypeScript passed; 15 unit tests passed; six existing browser regressions passed in Chrome, with the navigation regression expanded to all ten pages at 390px. Existing map checks also passed at 1920px and 1366px. Escape dismissal and focus return were separately confirmed in the browser. Production build includes all ten routes.

Protected files: all 16 previously existing API/contracts and workspace route/layout files remain byte-for-byte unchanged. Browser regressions use existing fixture mode, not live backend validation.

Screenshots: output/playwright/phase2/assets-desktop.png and regression screenshots in the same directory.

Stopped after Phase 2. Phase 3 requires approval and the backend endpoint contracts for each module.
