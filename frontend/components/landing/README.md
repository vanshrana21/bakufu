# BAKUFU landing story

Only app/page.tsx composes these ten chapters. story.module.css is isolated from
workspace styles; the new global variables do not replace workspace tokens.
All mineral art is original SVG. The animated 32×32 field uses a DPR-capped canvas.
ScrollTrigger is included in the gsap package.

## Evidence and interpretation

- LOBO AUC 0.9034: SIH26009_PROJECT_STATE.md, reported spatial validation.
- 123 months: backend/BOOTSTRAP.md, MSMP production series.
- 1,024 cells: backend/docs/phase_4/v6_promotion_verification.md.
  The landing draws an explicitly illustrative 32×32 field, not those results.
- Four model roles follow the provided product architecture, not a live-status check.
- 80% intervals: existing forecasting product specification.
- 0.84 → 0.00, attribution bars, forecast path, 32% risk and rule clauses are
  labelled illustrations. They are not a live API response or an ore estimate.
- BSE inputs are production filings; spatial and temporal features are separate.
- Feedback produces reviewed training candidates, never guaranteed improvement.

## Motion and accessibility

Final content is rendered by default. Reduced motion disables GSAP and the ticker.
Desktop chapters pin only on viewports at least 1100×820 and only when their
content fits. Touch-sized screens read as normal document flow. All ten module
links and both workspace entrances use the existing routes.

## Verification (2026-09-13)

- TypeScript check passed in the source checkout.
- Production build passed in /tmp/bakufu-landing-verify, isolated from live dev.
- 15 existing unit tests passed.
- All ten workspace routes on port 3001 returned 200 and rendered their headings
  with no uncaught browser errors. Live-data pages retain existing API delays.
- Desktop 1920×1080: all three pins active, no horizontal overflow.
- Mobile 390×844 / reduced motion: no pins, no horizontal overflow.
- Protected routes, API code, contracts, hooks, stores and shell matched pre-edit hashes.
- Screenshots: output/playwright/bakufu/.

## Local preview note

Port 3001 is the existing workspace development checkout. The unrelated training
app already owns IPv4 127.0.0.1:3000; it was left running. The landing production
preview binds IPv6 [::1]:3000 from the isolated build copy. localhost:3000 was
verified in Chrome; http://[::1]:3000 is the explicit address if IPv4 wins lookup.
The preview copy must be resynced/rebuilt to show later edits. Do not run a Next
production build against the same .next directory as a running dev server.
