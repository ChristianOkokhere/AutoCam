---
id: cinematic.teal_and_orange
tags: [cinematic, color_grade, teal, orange, film_look]
trigger_keywords: [teal and orange, cinematic, hollywood, film look, blade runner, deakins]
---

# Teal-and-orange cinematic

## When to reach for this

- The user names "teal and orange", "cinematic", or "film look".
- The photo has separable highlights (warm subjects) and shadows (cool
  environment) the look can hang on.

## Decision tree

We don't have a dedicated colour-grading op yet — we imitate it by
nudging the per-channel curves.

1. **Set the foundation.** Mild contrast bump first:
   `tone_contrast(amount=+10..+20)`. Without contrast, the grade looks
   like haze.
2. **Push orange into the highlights.**
   - `curve_rgb(channel="r", points=[[0,0], [0.5,0.52], [1,1]])`
   - `curve_rgb(channel="b", points=[[0,0], [0.7,0.65], [1,1]])`

   That's: lift R slightly across the top half, pull B slightly across
   the upper third.
3. **Push teal into the shadows.**
   - `curve_rgb(channel="b", points=[[0,0.05], [0.3,0.32], [1,1]])`
   - `curve_rgb(channel="r", points=[[0,0], [0.3,0.27], [1,1]])`

   B+ in shadows, R– in shadows. Don't go heavy — `0.05` lift on the
   black point is plenty.
4. **Cool the global white-point a touch.**
   `color_white_balance(temp_shift=-3..-8, tint=0..+3)`.
5. **Vibrance, not saturation.** `color_vibrance(amount=10..20)` so the
   look doesn't fall apart on skin.

## Pitfalls

- Stacking too many `curve_rgb` calls on the same channel. The piecewise
  interp compounds — keep adjustments to one curve per channel per
  recipe pass.
- Pushing the teal into already-blue shadows turns them ink-black. Read
  the histogram and back off if `b.p05` already sits near zero.
- "Cinematic" doesn't mean dark. The photo should still read clearly.

## Stop when

- Skin tones lean warm-orange but still look like skin.
- Shadows have a cool cast without going Smurf-blue.
- The photo could plausibly be a frame from a film without being an
  obvious filter.
