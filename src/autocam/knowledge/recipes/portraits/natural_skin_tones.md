---
id: portrait.natural_skin_tones
tags: [portrait, skin, color]
trigger_keywords: [portrait, skin, people, face, headshot]
---

# Natural skin tones

## When to reach for this

- The subject is a person and skin is visible.
- Skin looks muddy, overly red, jaundiced, or lifeless.
- Mixed lighting (window + tungsten, etc.) has thrown off the WB.

## Decision tree

1. **Read the histogram first.** Underexposed skin is dim, not warm —
   fix exposure before anything else.
2. **WB it.** A small `color_white_balance(temp_shift=+5..+15, tint=-2..+5)`
   usually warms skin without going orange. Negative `tint` if magenta.
3. **Lift shadows lightly.** `tone_shadows(amount=10..20)` opens the eye
   sockets and fills detail without flattening the photograph.
4. **Pull highlights if blown.** Sun-side cheekbones near `p95 = 1` get a
   `tone_highlights(amount=-15..-30)`.
5. **Add a touch of vibrance, not saturation.** `color_vibrance(amount=8..15)`
   brings the surroundings up without pushing skin further into orange.

## Pitfalls

- Cranking `color_saturation` makes skin look sunburned. Always vibrance
  first.
- Overdone `tone_shadows` lift kills the modeling that makes a face look
  3D. If the photo is going flat, back off.
- Strong `tone_contrast` on a portrait crushes skin tonality. Prefer a
  gentle S-curve via `curve_rgb` if you need shape.

## Stop when

- Skin reads as living tissue (not orange, not green, not corpse-pale).
- Eye whites are neutral, not yellow.
- The histogram's red `p95` isn't materially higher than green's.
