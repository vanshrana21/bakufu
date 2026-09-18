# Frontend Guidance — Colouring the Prospectivity Heatmap

**For:** whoever renders `GET /prospectivity/heatmap` (contract section 10).
**Model:** `prospectivity_v6`, scored from `s2_moil_operational_v1.tif`. Scores are capped at `0.99`.
**Measured:** 2026-09-13, after the serving-mosaic fix (known issue #7).

This is guidance, not backend behaviour. The API returns raw scores; how they
are coloured is the frontend's decision. The recommendation comes from the
score distributions the API actually serves.

> **Correction.** An earlier version of this document quoted 24.5% of cells
> ≥ 0.90 and recommended breakpoints at 0.20 / 0.50 / 0.75 / 0.90. Those
> figures came from the wrong mosaic: the API was scoring
> `s2_nagpur_smoke_test.tif`, not the mosaic v6 was trained on, and a quarter
> of the belt-wide cells were scored from blank pixels. Every number below is
> re-measured from the corrected serving mosaic.

---

## TL;DR

1. **Do not use a linear 0–0.99 colour ramp.**
2. Use **five fixed bins** with these breakpoints:

   | score | colour | legend label |
   |---|---|---|
   | `0.00 – 0.10` | grey `#9e9e9e` | Low |
   | `0.10 – 0.35` | blue `#4575b4` | Moderate |
   | `0.35 – 0.70` | yellow `#fee090` | Elevated |
   | `0.70 – 0.95` | orange `#fc8d59` | High |
   | `0.95 – 0.99` | red `#d73027` | Very high (legend max reads **"≥ 0.95, cap 0.99"**) |

3. Render `null` cells as **transparent** (or a hatch), never grey.
4. Keep the breakpoints **fixed across viewports**. Do not recompute them per view.

---

## The served distribution

Warm viewports, `grid_size=32`, `mask=none`. Every cell has real imagery, so
none are `null`.

| viewport | bbox | ≥ 0.90 | ≥ 0.75 | exactly at the 0.99 cap | median |
|---|---|---|---|---|---|
| `full_bbox` | `[79.0, 21.3, 80.6, 22.1]` | **27.2%** | 36.6% | 19.1% | 0.54 |
| `balaghat_bhandara` | `[79.53, 21.32, 80.57, 22.05]` | **23.9%** | 35.5% | 16.9% | 0.54 |
| `balaghat_ukwa` | `[80.05, 21.70, 80.60, 22.05]` | **43.9%** | 58.1% | 33.1% | 0.85 |

Quantiles:

| viewport | 10th | 20th | 40th | 60th | 80th | 90th |
|---|---|---|---|---|---|---|
| `full_bbox` | 0.04 | 0.10 | 0.35 | 0.70 | 0.97 | 0.99 |
| `balaghat_bhandara` | 0.05 | 0.12 | 0.38 | 0.69 | 0.95 | 0.99 |
| `balaghat_ukwa` | 0.16 | 0.36 | 0.73 | 0.95 | 0.99 | 0.99 |

The distribution is **spread across the whole range with a spike at the
cap**, not clustered in the middle. That has two consequences:

- **A linear ramp wastes most of its range.** On `full_bbox` about 36% of
  cells land in the top quarter of the ramp, and 19% are at one identical
  maximum colour.
- **The top cannot be subdivided.** Of the 226 `full_bbox` cells ≥ 0.95, there
  are only 31 distinct values, and most cells are exactly 0.99. More bins
  above 0.95 would just split identical values. The top bin is a ceiling,
  so treat it as one class.

## Recommended: fixed breakpoints at 0.10 / 0.35 / 0.70 / 0.95

These are the `full_bbox` quintiles, rounded. They split the belt-wide map
into roughly equal fifths:

| bin | `full_bbox` | `balaghat_bhandara` | `balaghat_ukwa` |
|---|---|---|---|
| grey `0.00–0.10` | 19.2% | 17.0% | 7.4% |
| blue `0.10–0.35` | 20.9% | 20.6% | 12.1% |
| yellow `0.35–0.70` | 19.2% | 23.3% | 18.8% |
| orange `0.70–0.95` | 18.6% | 19.1% | 22.5% |
| red `0.95–0.99` | 22.1% | 19.9% | 39.3% |

For comparison, the earlier breakpoints (0.20 / 0.50 / 0.75 / 0.90) on the
same data leave orange with 9.4% of `full_bbox` and put 29.1% in grey:

| bin | `full_bbox` | `balaghat_bhandara` | `balaghat_ukwa` |
|---|---|---|---|
| grey `0.00–0.20` | 29.1% | 27.6% | 11.2% |
| blue `0.20–0.50` | 18.9% | 19.7% | 15.8% |
| yellow `0.50–0.75` | 15.3% | 17.1% | 14.8% |
| orange `0.75–0.90` | 9.4% | 11.6% | 14.2% |
| red `0.90–0.99` | 27.2% | 23.9% | 43.9% |

**Why fixed rather than per-viewport quantiles:** `balaghat_ukwa` is much
hotter than the belt as a whole (median 0.85 against 0.54). Per-view
quantiles would repaint the same ground a different colour after panning, and
a user comparing two areas would be comparing two scales. With fixed
breakpoints, Ukwa correctly reads as mostly orange and red. That is the
model's view of that ground, not a rendering artefact.

```ts
const BINS = [
  { max: 0.10, color: "#9e9e9e", label: "Low" },
  { max: 0.35, color: "#4575b4", label: "Moderate" },
  { max: 0.70, color: "#fee090", label: "Elevated" },
  { max: 0.95, color: "#fc8d59", label: "High" },
  { max: Infinity, color: "#d73027", label: "Very high" },
];

function cellColor(score: number | null): string | null {
  if (score === null) return null;              // no imagery: leave transparent
  return BINS.find((b) => score < b.max)!.color;
}
```

## Alternative: continuous logit ramp

For a smooth gradient instead of bins, map the score through a logit before
applying a continuous colour scale:

```
display = log(p / (1 − p))
```

Clamp `p` first. Scores run from about `0.001` up to the `0.99` cap, so the
display range is about **−6.9 to +4.6**. The logit stretches both tails.
The spike at 0.99 still renders as one colour, which is correct, since those
cells are tied.

```ts
const logit = (p: number) => {
  const c = Math.min(Math.max(p, 0.001), 0.99);
  return Math.log(c / (1 - c));
};
// feed logit(score) into a sequential scale with domain [-6.9, 4.6]
```

The recommended bins correspond to logit breakpoints at −2.20, −0.62, 0.85
and 2.94, so both approaches can share a legend.

## Rendering the other cell states

These rules come from contract section 10 and apply whichever ramp you choose:

| value | meaning | render |
|---|---|---|
| `null` | no real imagery: outside the served mosaic, or a gap where a band is missing or zero | transparent or hatched, **never** grey (grey means "Low") |
| `0.0` | genuine low score, or excluded by a mask | bottom bin |
| `0.0 < s ≤ 0.99` | real score | binned as above |

With `mask=geological`, `occurrence_buffer` or `both`, many cells become
exactly `0.0` and fall into grey. That's correct: "excluded by geology" is a
finding. Consider a legend note such as *"grey includes masked-out ground"*
when a mask is active.

## Legend wording

- Label the top bin **"≥ 0.95 (cap 0.99)"**, never "1.0". The API caps scores
  at 0.99 (`score_range.cap`).
- Call the values **relative prospectivity**, not "probability of a deposit".
  They come from a positive-unlabelled model and have not been calibrated
  against drilling outcomes. Read them as a ranking of ground.
- Re-measure these distributions if the model or serving mosaic changes; the
  last change moved `balaghat_ukwa` from 8.6% to 43.9% of cells ≥ 0.90.
