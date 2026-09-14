# Mineral Intelligence Command Center — Phase 1

The active foundation is defined in `app/globals.css` and `tailwind.config.ts`.
The exact tokens, component contracts and review decisions are in
`docs/PHASE_1_DESIGN_SYSTEM.md`. Noto Sans Variable and JetBrains Mono Variable
are self-hosted. Dark analytical surfaces are explicit opt-in scopes; light
surfaces remain the default. Existing layout composition and data integrations
are retained until the next approved phase.

The earlier composition reference below describes legacy pages, not requirements
for new enterprise routes. Its previous font and motion notes are historical.

---

# Earth Observatory — precision industrial

The current direction. It supersedes the Survey Edition (burgundy/cream editorial) study,
which in turn superseded the graphite/oxide study archived in docs/DESIGN_RESEARCH.md.

Reference: https://sstr.tech — an engineering-products site whose restraint, not whose
layout, is what we borrow. Their page is 12,000px of marketing narrative; ours is a
working instrument. What transfers is the material character and the motion discipline.

## Identity
Neutral mineral grey (`#EFF0F1` page, `#FAFBFB` panels) against graphite instrument
surfaces (`#18191B`). A single concentrated orange (`#FE5B2A` brand, `#C44016` primary)
marks the selected thing and the primary action — never a status. Borders are exactly 1px:
`#C3C4C8` on light, `#2F3032` on dark. `app/globals.css` is the token source of truth;
`components/operations/operations.css` scopes the operational page composition.

Semantic and data colors (success / warning / critical, the prospectivity ramp, chart
series) are deliberately independent of the brand accent, so rebranding can never change
what a color asserts about evidence.

## Typography
Self-hosted Noto Sans, with a mono stack (`JetBrains Mono`, `SF Mono`, Menlo) for
coordinates, identifiers, dates and tabular figures.

- Display / page titles: uppercase, **weight 400**, `-0.035em`, line-height 1.02. Never bold — size does the work.
- Micro-labels: 10px, weight 500, `+0.1em`, uppercase.
- Figures: weight 400, `-0.035em`, set solid, always `tabular-nums`.

## Motion
Three effects, and nothing else. Every one is either scrubbed to scroll, played once on
entry, or driven by real data — the properties that separate this from decorative motion.

| Effect | Where | Rule |
| --- | --- | --- |
| `Reveal` | briefing, production, actions panels | one-time, 420ms, fires 300px early so fast scrolling never meets a blank panel |
| `Odometer` | the four vital signs | wheels roll to the true value, 420ms |
| `SpecimenDrift` | Command Center specimen only | the sole scroll-scrubbed movement, ±10px |

**Nothing carrying data moves on scroll.** The Explorer has no entrance motion at all: it
is the operable instrument and must be usable the instant it paints.

Motion is opt-in through a `.motion-ready` class set by a synchronous head script, so
no-JS, print, reduced motion and a failed observer all render the complete briefing.
Evidence is never hidden because an animation did not run, and an odometer wheel can
never come to rest on a digit that is not the data.

## Four views
- Command Center: hero, four vital signs, forecast/uncertainty, screening register, review register.
- Explorer: survey controls + inspector, dominant map canvas, outlook column, review register.
- Production & Risk: dark forecast-basis rail, forecast and risk instruments, evidence band.
- Corrective Actions: dark review docket, selected rule evidence, decision protocol, selectable register.

## Honesty invariants
Unchanged by any restyling. Scope nulls stay distinct from policy zeros. Ghost membership
is waste/slag ∩ fixture 5km membership ∩ geographic scope, independent of mask toggles.
Hatching means exclusion, not geological absence. Risk is relative to an issued forecast,
not buyer demand. Review records are proposals and are never shown as executed.
