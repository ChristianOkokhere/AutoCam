---
id: landscape.golden_hour
tags: [landscape, sunset, sunrise, golden_hour, warm]
trigger_keywords: [golden hour, sunset, sunrise, warm, glow, magic hour]
---

# Golden hour landscape

## When to reach for this

- Outdoor scene, low sun, warm directional light.
- The user wants the warmth in the photo to feel **deserved** — not faked.

## Decision tree

1. **Don't strip the warmth.** A scene shot in golden hour is *supposed*
   to be warm. Resist auto-WB instincts. If anything, push warmer:
   `color_white_balance(temp_shift=+10..+20, tint=0..+5)`.
2. **Dynamic range.** Golden-hour scenes typically have bright sky and
   dim foreground. Recover highlights, lift shadows:
   - `tone_highlights(amount=-25..-40)`
   - `tone_shadows(amount=+20..+35)`
3. **Build the glow.** A subtle S-curve through `curve_rgb` (on `rgb`
   channel) with one point lifted at ~`(0.25, 0.27)` and one pulled at
   ~`(0.75, 0.78)` adds the golden-hour bloom without clipping.
4. **Saturate selectively.** `color_vibrance(amount=15..25)` brings up
   greens / blues without further pushing the already-saturated warm
   foreground.
5. **Sharpen lightly at the end.** `detail_sharpen(amount=80, radius=1.0)`.

## Pitfalls

- Pushing `color_saturation` along with the warm WB cooks the image
  orange. Use vibrance instead.
- Lifting shadows beyond `+40` reveals shadow noise and kills the
  sculptural sun-direction the photo had going for it.
- Clipping the sun: if `p95 = 1` on red **and** green, you'll get a
  white blob where the sun should be. Recover with `tone_highlights`
  or accept it as a creative choice.

## Stop when

- Sky retains highlight texture (cloud detail, gradient).
- Foreground reads warm but not orange.
- The image looks like it was *shot* in golden hour, not retroactively
  Instagram-filtered.
