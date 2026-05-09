# Working color spaces

You don't see this directly — it shapes the math behind every op.

## Linear sRGB, float32, internally

The pipeline keeps pixels in **linear sRGB float32** through every op.
Photographic ops behave correctly there:

- Exposure is just `linear * 2**ev`. Doubling light is doubling pixel
  values.
- White balance is per-channel multiplication. Linear is the only place
  that cleanly preserves neutral mid-grays.
- Saturation and vibrance work against a luminance-weighted reference and
  preserve perceived brightness.

## Display sRGB at the boundaries

`io/image.py` converts at the I/O boundaries:

- On load: 8-bit display sRGB → linear float32.
- On save: linear float32 → 8-bit display sRGB.

Anything you see on screen is display gamma. If a tool result describes
"pixel values 0.5", that's display gamma — read it like you'd read a
histogram.

## Why some ops convert internally

A few ops convert to display gamma temporarily, do the math, and convert
back. That isn't a bug — it's the right place for that math.

- `tone_contrast` pivots around 0.5 in display gamma so the S-curve feels
  perceptually balanced. Doing it in linear would crush blacks far harder
  than highlights.
- `tone_highlights` / `tone_shadows` weight by display-gamma position
  (`> 0.5` is "highlights"), so the soft mask matches what the eye calls
  highlights and shadows.
- `curve_rgb` operates on display gamma points because that's what
  reference curves in Lightroom / Photoshop look like.

## What this means for tool calls

You don't need to think about which space an op runs in — they all consume
and return linear arrays. Just don't stack ops as if they're naïve adds.
A linear `+0.1` is a different magnitude than a display-gamma `+0.1`.

Trust the histogram summaries: they're reported in display gamma, the same
space you read on screen.
