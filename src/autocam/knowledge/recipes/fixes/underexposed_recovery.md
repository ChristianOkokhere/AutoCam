---
id: fixes.underexposed_recovery
tags: [fix, underexposed, dark, exposure, recovery]
trigger_keywords: [too dark, underexposed, dim, brighten, dark, lift, can't see]
---

# Underexposed photo recovery

## When to reach for this

- The histogram's mean is low (≤ 0.30 in display gamma).
- The user says "too dark", "can't see anything", "brighten".
- Highlights are fine but shadows are buried.

## Decision tree

1. **Diagnose the shortfall.** Estimate stops from the histogram:
   - Mean around `0.35` → about `+0.5 EV`
   - Mean around `0.25` → about `+1.0 EV`
   - Mean around `0.18` → about `+1.5 EV`. Beyond that, you'll get noise.
2. **Lift exposure first.** `tone_exposure(ev=+0.5..+1.5)`. Resist the
   urge to push `+2` — that amplifies sensor noise.
3. **Recover any new highlights.** After exposure, re-read the histogram.
   If `p95 > 0.95` on any channel, pull `tone_highlights(amount=-15..-30)`.
4. **Open shadows further.** `tone_shadows(amount=+15..+30)` for what's
   still buried after the exposure lift.
5. **Restore black point.** Pulling exposure up tends to turn blacks
   grey. `tone_blacks(amount=-10..-20)` brings them back.
6. **Optional contrast restore.** Recovered photos look flat. A gentle
   `tone_contrast(amount=+10..+15)` or a soft S-curve via `curve_rgb`
   adds bite back.

## Pitfalls

- Pushing exposure past the noise floor. If the photo is clearly noisy
  after `+1 EV`, stop — say so to the user. We don't have noise reduction
  in v1.
- Lifting shadows without restoring blacks → the photo looks washed
  out, like fog.
- Boosting saturation to "make up for" a flat recovered photo. Contrast
  is the right answer; saturation just hides the problem.

## Stop when

- The subject is clearly visible.
- The histogram is no longer leaning hard left — `p50` near `0.45–0.55`.
- Blacks read black, not grey.
