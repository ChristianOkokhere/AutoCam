"""Tests for the mask ops."""

from __future__ import annotations

import numpy as np

from autocam.ops import (
    ColorRangeMaskOp,
    ExposureOp,
    InvertMaskOp,
    LuminosityMaskOp,
    PipelineCtx,
)


def _ctx() -> PipelineCtx:
    return PipelineCtx(source_path="<mem>")


def test_luminosity_mask_emphasises_highlights() -> None:
    # Gradient from black at left to white at right, in linear sRGB.
    h, w = 8, 16
    xs = np.linspace(0.0, 1.0, w, dtype=np.float32)
    img = np.tile(xs[None, :, None], (h, 1, 3)).astype(np.float32)

    op = LuminosityMaskOp(range="highs", feather=0.0)
    ctx = _ctx()
    op.apply(img, ctx)
    mask = ctx.masks[op.id]

    assert mask.shape == (h, w)
    assert mask.dtype == np.float32
    # Mask near 0 on the dark side, near 1 on the bright side.
    assert mask[:, 0].mean() < 0.05
    assert mask[:, -1].mean() > 0.95


def test_luminosity_mask_shadows_inverts_curve() -> None:
    h, w = 8, 16
    xs = np.linspace(0.0, 1.0, w, dtype=np.float32)
    img = np.tile(xs[None, :, None], (h, 1, 3)).astype(np.float32)

    op = LuminosityMaskOp(range="shadows", feather=0.0)
    ctx = _ctx()
    op.apply(img, ctx)
    mask = ctx.masks[op.id]

    assert mask[:, 0].mean() > 0.95
    assert mask[:, -1].mean() < 0.05


def test_color_range_mask_targets_hue_cluster() -> None:
    h, w = 6, 6
    img = np.zeros((h, w, 3), dtype=np.float32)
    # Top half: bright red. Bottom half: bright green.
    img[: h // 2, :, 0] = 1.0
    img[h // 2 :, :, 1] = 1.0

    op = ColorRangeMaskOp(hue_deg=0.0, hue_width_deg=20.0, feather=0.0, sat_min=0.05)
    ctx = _ctx()
    op.apply(img, ctx)
    mask = ctx.masks[op.id]

    assert mask[: h // 2, :].mean() > 0.9
    assert mask[h // 2 :, :].mean() < 0.1


def test_invert_mask_complements_base() -> None:
    h, w = 4, 4
    img = np.full((h, w, 3), 0.5, dtype=np.float32)
    base = LuminosityMaskOp(range="highs", feather=0.0)
    ctx = _ctx()
    base.apply(img, ctx)

    inv = InvertMaskOp(target=base.id)
    inv.apply(img, ctx)

    out_base = ctx.masks[base.id]
    out_inv = ctx.masks[inv.id]
    np.testing.assert_allclose(out_base + out_inv, 1.0, atol=1e-6)


def test_executor_applies_op_through_mask(fixture_jpeg) -> None:
    """A masked exposure should brighten only where the mask is high."""
    from autocam.pipeline.executor import run_stack
    from autocam.pipeline.stack import EditStack

    stack = EditStack(source=str(fixture_jpeg))

    # Build a mask that's full-on in the right half via color_range tuned wide
    # — actually simpler: use luminosity over a known fixture. The fixture is
    # a gradient; "highs" → bright on the right.
    mask_op = LuminosityMaskOp(range="highs", feather=0.0)
    stack.append(mask_op)

    expo = ExposureOp(ev=2.0, mask=mask_op.id)  # +2 stops, but only on highs
    stack.append(expo)

    out = run_stack(stack, preview=True)

    # Left edge stays close to source; right edge gets the exposure boost.
    _, w, _ = out.shape
    left_mean = out[:, : w // 8].mean()
    right_mean = out[:, -w // 8 :].mean()
    assert right_mean > left_mean * 1.5


def test_executor_raises_on_unknown_mask_id(fixture_jpeg) -> None:
    """Adjustment op referencing a non-existent mask should raise."""
    import pytest

    from autocam.pipeline.executor import run_stack
    from autocam.pipeline.stack import EditStack

    stack = EditStack(source=str(fixture_jpeg))
    stack.append(ExposureOp(ev=0.5, mask="does-not-exist"))

    with pytest.raises(KeyError, match="does-not-exist"):
        run_stack(stack, preview=True)
