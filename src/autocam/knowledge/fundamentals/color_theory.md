# Color theory

## Temperature & tint

`color_white_balance` has two knobs:

- `temp_shift` in `-100..+100`: positive warms (more red, less blue),
  negative cools. Each ±100 corresponds to roughly ±500K of white-point
  shift in feel — not exact Kelvin.
- `tint` in `-100..+100`: positive pushes magenta, negative pushes green.

If skin looks jaundiced or sunsets look orange-pink, the tint axis is
usually doing it — not temp.

## Saturation vs vibrance

- `color_saturation` is a flat multiplier away from luminance. Touch it
  for a global "more colour, less colour" feel. Easy to clip.
- `color_vibrance` eases off on already-saturated pixels (typically skin
  and sky on a sunny day) and pushes the rest. Reach for it when the photo
  has one strong colour and you want the rest to come up to meet it.

`vibrance > saturation` for portraits. `saturation > vibrance` for graphic
or product work.

## Hue clusters worth knowing

Hue values are 0–360°:

| Subject              | Hue cluster        |
|---                   |---                 |
| Caucasian skin       | `15–35°`            |
| Asian / olive skin   | `20–45°`            |
| Foliage (green)      | `90–150°`           |
| Open sky (clear)     | `210–230°`          |
| Sunset / sunrise sky | `15–60°` and `300+°` |

The HSL op isn't in the v1 tool surface (Phase 6+); for now you steer
these clusters with `color_white_balance`, `color_saturation`, or curves
on individual channels.

## Color grading the simple way

We don't have a 3-way colour-grading op yet. To imitate one:

- Cool the shadows + warm the highlights → use `curve_rgb` per channel.
  R+ in highlights, B+ in shadows. Pull complementary curves on the other
  channel for separation.
- Teal-and-orange: orange in highlights / midtones (R+, G slight+, B–),
  teal in shadows (B+, G slight+, R–). Subtle, maybe 5–10 points each.

## Don't

- Don't ramp saturation past `+30` globally — colour clips or starts to
  posterise. Layer multiple gentle pushes if you really need more.
- Don't WB-shift to compensate for a tonal problem. If a photo looks dull,
  it's probably exposure / contrast — not WB.
- Don't stack two `color_white_balance` calls in a row. Make one decisive
  shift; if it's wrong, undo it.
