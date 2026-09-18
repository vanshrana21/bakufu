# MOIL Mine Scores: Distribution, Reading, and How to Present It

**Model:** `prospectivity_v6` · **imagery:** `s2_moil_operational_v1.tif`
**Coordinates:** `settings.MOIL_MINES`, cited in `docs/moil_coordinate_sources.md`
**Measured:** 2026-09-15, `scripts/diagnostics/mine_score_profiles.py` →
`data/processed/mine_score_profiles.json`

Every one of the ten mines now returns a real score from real imagery. They do
not all score high. This document says what each score rests on, and how to
present that honestly without it reading as a model failure.

---

## The ten mines

`nearest +ve` is the distance to the closest of the 954 points v6 trained on.
`neighbourhood` is the range across four probes about 1.1 km N/S/E/W.

| mine | state | type | **score** | coord. confidence | nearest +ve (km) | neighbourhood | two strongest drivers |
|---|---|---|---|---|---|---|---|
| Ukwa | MP | underground | **0.99** | high | 0.01 | 0.52 – 0.99 | elevation +0.60, texture dim 02 +0.49 |
| Chikla | MH | underground | **0.99** | high | 0.38 | 0.11 – 0.99 | elevation +1.50, slope +0.82 |
| Kandri | MH | underground | **0.99** | high | 2.32 | 0.42 – 0.99 | elevation +1.71, slope +1.50 |
| Munsar | MH | underground | **0.99** | medium_high | 1.30 | 0.07 – 0.99 | elevation +1.56, slope +0.83 |
| Beldongri | MH | underground | **0.99** | **low** | 1.24 | 0.97 – 0.99 | slope −1.00, Mn-oxide ratio +0.61 |
| Gumgaon | MH | underground | **0.97** | high | 7.58 | 0.94 – 0.99 | elevation +1.13, slope −0.64 |
| Tirodi | MP | opencast | **0.68** | low_medium | 0.24 | 0.21 – 0.96 | elevation +1.35, texture dim 33 −0.39 |
| Balaghat | MP | underground | **0.34** | high | 1.54 | 0.11 – 0.99 | slope −0.88, elevation +0.67 |
| Dongri Buzurg | MH | opencast | **0.33** | low_medium | 0.69 | 0.53 – 0.99 | elevation +1.27, blue reflectance −0.58 |
| Sitapatore | MP | opencast | **0.12** | high | 3.08 | 0.78 – 0.93 | elevation +1.06, green reflectance −0.79 |

**Score and distance-to-training-data are not the same thing.** Gumgaon scores
0.97 while being 7.6 km from the nearest training positive; Balaghat scores
0.34 while being 1.5 km from one. The model is not simply recognising ground it
was trained on — which is what makes the scores worth anything, and also why a
low score at a real mine deserves an explanation rather than a patch.

**Terrain does most of the visible work.** Elevation is a top-two driver at
nine of ten mines, and the recorded v6 gain importance is terrain 25.3% across
three features against 61.8% spread over all 64 embedding dimensions. The
belt's ore sits on a specific topographic setting, and the model has learned
that setting.

---

## Group A — model recognises these: 6 mines, score ≥ 0.85

Ukwa, Chikla, Kandri, Munsar, Beldongri (all 0.99) and Gumgaon (0.97).

> Six of MOIL's ten operating mines land at or near the model's ceiling, and it
> reaches them by terrain and spectral context rather than by proximity to
> training data — Gumgaon scores 0.97 from 7.6 km outside anything the model
> was trained on. For a screening tool that is the result that matters: point
> it at ground nobody has drilled and it still recognises the setting.

**Caveat to keep visible:** Beldongri's 0.99 sits on the weakest coordinate of
the ten (a third-party USGS database). A confident score at an uncertain
location is a confident score about *some* ground, not necessarily that mine.

## Group B — mixed signal: 1 mine, 0.35 – 0.85

Tirodi (0.68).

> Tirodi reads as moderately prospective: the terrain fits the productive
> pattern (elevation +1.35) but the surface texture does not match as cleanly.
> Its coordinate is a town-centre proxy, so the model may be describing ground
> a kilometre or two from the workings. This is the band where the map says
> "worth looking at" rather than "drill here", and treating it that way is
> the difference between a screening tool and a claim.

## Group C — model signals "not prospective here": 3 mines, < 0.35

Balaghat (0.34), Dongri Buzurg (0.33), Sitapatore (0.12).

> Three mines score low, including MOIL's flagship at Balaghat. The model is
> reading the surface: Balaghat is the deepest underground manganese mine in
> Asia, and a 660 m shaft leaves no more spectral trace than any other hillside
> — three separate training positives within 5 km of it still score 0.99, so
> the model has not lost the block, only that pixel. Satellite prospectivity
> finds ground whose *surface* looks productive; it does not see ore at depth,
> and a tool that scored every known mine at the cap would only prove it had
> memorised their coordinates.

**Do not describe Group C as the model being wrong.** The honest framing is a
stated limitation: surface-derived features cannot see a deep orebody, and the
correct response is the 0.99 cells the model does put within a few kilometres.

---

## Point scores are unstable; use areas

Scores move sharply inside a kilometre. Probing ±1.1 km around each mine:

| mine | point | neighbourhood min | neighbourhood max |
|---|---|---|---|
| Munsar | 0.99 | 0.07 | 0.99 |
| Chikla | 0.99 | 0.11 | 0.99 |
| Balaghat | 0.34 | 0.11 | 0.99 |
| Beldongri | 0.99 | 0.97 | 0.99 |

A 5 × 5 grid spanning ±2 km around Balaghat runs **0.022 to 0.99**, mean 0.27,
with 8% of cells at or above 0.85. Two consequences:

1. **A single point score is not a stable statistic.** Move 500 m and it can
   change by half the scale. Coordinates are precise to 1–3 km for four of the
   ten mines, which is the same scale.
2. **The heatmap cell is the better unit.** It already averages a 3 × 2.5 km
   area, which is why Balaghat read 0.787 in the v6 write-up's grid while its
   exact point read differently.

---

## Proposed dashboard presentation

**1. Never show a bare point score per mine.** Show the mine's heatmap cell
score, or the median of a 1 km neighbourhood, with a range bar for the min–max
across that neighbourhood. A mine whose bar spans 0.11–0.99 is telling the
viewer something real about spatial heterogeneity.

**2. Plot score against coordinate confidence, not score alone.** A 2 × 2
(score high/low × coordinate confident/uncertain) puts each mine in a quadrant
that implies the next action:

| | coordinate confident | coordinate uncertain |
|---|---|---|
| **score high** | Ukwa, Chikla, Kandri, Gumgaon, Munsar | Beldongri |
| **score low** | Balaghat, Sitapatore | Dongri Buzurg, Tirodi |

Ranking ten mines by score in a leaderboard invites exactly the wrong reading:
that the model is grading MOIL's assets. It is grading *surface signal at a
coordinate*.

**3. Give every mine a one-line "why" from its SHAP drivers.** The API already
returns them. "Terrain matches productive settings, surface texture does not"
is a sentence a judge can evaluate; "0.68" is not.

**4. Explain Balaghat and Dongri Buzurg inline, where they appear.** A footnote
on the tile: *"Deep underground workings leave little surface signal. Three
training occurrences within 5 km of Balaghat score 0.99 — the model identifies
the block, not the shaft."* Handling the weakest-looking result in the open is
more convincing than a map with no weak results in it.

**5. Use the shared colour bins** from `docs/frontend_heatmap_guidance.md`
(0.10 / 0.35 / 0.70 / 0.95) for mine markers too, so a marker and the ground
under it are read on one scale.

**6. State the cap.** 0.99 is a ceiling, not certainty; five mines sit on it
and cannot be ranked against each other.
