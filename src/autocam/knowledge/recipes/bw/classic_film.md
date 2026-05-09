---
id: bw.classic_film
tags: [black_and_white, monochrome, film, contrast]
trigger_keywords: [black and white, b&w, bw, monochrome, film, tri-x, ilford]
---

# Classic film black-and-white

## When to reach for this

- The user asks for a "black-and-white", "B&W", or names a film stock.
- The photo's color isn't carrying it — graphic shape, light, and texture
  are.

## Decision tree

We don't have a dedicated `color_to_bw` op yet (it's Phase 6+). Imitate
the conversion by neutralising saturation through contrast and curves:

1. **Kill colour, keep tonality.** `color_saturation(amount=-100)` — flat
   greyscale. This is a starting point, not the destination.
2. **Set black point.** `tone_blacks(amount=-15..-30)`. Classic film has
   a real black somewhere in the frame; the histogram's `p05` should
   touch 0 on at least one part.
3. **Set white point.** `tone_whites(amount=+5..+20)`. There should be a
   real white somewhere — specular reflection, sky, edge of a face.
4. **Build contrast through curves.** `curve_rgb` with points like
   `[[0,0], [0.25,0.18], [0.5,0.5], [0.75,0.82], [1,1]]` — S-curve,
   pivots at midtones. Adjust the ends for grit (steeper) or softness
   (gentler).
5. **Optional grain via sharpen.** `detail_sharpen(amount=120, radius=0.8)`
   gives a film-like crispness without inventing grain we don't have.

## Pitfalls

- Skipping black/white-point setting leaves the image looking like a
  *desaturated colour photo*, not a B&W.
- Heavy contrast on faces buries skin tones. If the subject is a person,
  pull the contrast back — `(0.25, 0.22)` not `(0.25, 0.15)`.
- Don't push saturation back up "a touch". Either fully B&W or don't.

## Stop when

- The image has a real black, a real white, and rich greys in between.
- The shapes carry the photo. If you find yourself missing the colour,
  this isn't the right photo for B&W.
