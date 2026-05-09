# Exposure

## Stops, linearly

Exposure is multiplicative in linear light. One stop is `2x`. `+1 EV` doubles
linear light; `-1 EV` halves it. AutoCam's `tone_exposure` is implemented as
exactly that — `linear * 2**ev` — so a half stop (`ev=0.5`) is a 1.41× boost.

This is *not* the same as adding a constant in display gamma. If a photo looks
half a stop too dim, reach for `tone_exposure`, not `tone_brightness` or a
curve nudge.

## Tonal regions

Read in **display gamma** (what the eye sees), in `[0, 1]`:

| Region     | Approx range | Reach for                 |
|---         |---           |---                         |
| Blacks     | `0.00–0.10`  | `tone_blacks`             |
| Shadows    | `0.10–0.40`  | `tone_shadows`            |
| Mids       | `0.40–0.65`  | `tone_contrast`, curves   |
| Highlights | `0.65–0.90`  | `tone_highlights`         |
| Whites     | `0.90–1.00`  | `tone_whites`             |

`shadows` and `highlights` ride a soft mask centered on their region — they
won't fight the global exposure if you nudge gently. Don't use them for global
brightness; use exposure.

## Reading a histogram summary

The tool result contains per-channel `mean`, `p05`, `p50`, `p95` in display
gamma. Useful diagnostics:

- **`p05` near 0 on all channels** → blacks are clipping. Pull `tone_blacks`
  positive, or back off whatever you just did to the shadows.
- **`p95` near 1 on a single channel** → that channel's highlights are blown.
  Pull `tone_highlights` negative, or use `color_white_balance` if it's a
  red/blue cast doing it.
- **All `p50` near 0.5** with low `p95` → flat midtones, low contrast. Reach
  for `tone_contrast` or a soft S-curve.
- **`mean` of all channels equal** doesn't mean the WB is right; it just means
  the per-channel averages match — could still have a cast in skin or sky.

## When to layer ops

- Recover before pushing. Pull `tone_highlights` down before bumping global
  exposure, otherwise you push clipped pixels further.
- Set a black point with `tone_blacks` before contrast, otherwise contrast
  pivots around an unstable midpoint.
- Save white-balance for after exposure — `color_white_balance` shifts
  channels multiplicatively, so its strength scales with overall brightness.

## Don't

- Don't add `tone_exposure` repeatedly to climb a stop. One call with the
  right `ev` is the right answer; chaining tiny ones is noisy.
- Don't use curves to fix a global exposure problem. Exposure first, curves
  for shape.
