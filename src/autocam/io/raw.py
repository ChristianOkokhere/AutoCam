"""RAW image I/O via rawpy.

Returns the same ``(H, W, 3)`` linear-sRGB float32 array shape as
:func:`autocam.io.image.load_image`, so the pipeline doesn't need to know
whether the source is a RAW or a JPEG.

We always ask rawpy for 16-bit linear output (``gamma=(1, 1)``,
``output_bps=16``) in the sRGB primaries. The pipeline handles tonal /
colour ops from there. ``preview=True`` switches on rawpy's ``half_size``
demosaic for ~4x faster previews; the executor still clamps the long edge.

We deliberately don't expose every rawpy knob today — the goal of this
phase is "open a RAW and edit it", not a Lightroom-style develop UI. The
develop knobs (white balance, highlight recovery, custom demosaic) come
back as op-stack ops in a follow-up.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import numpy.typing as npt
import rawpy

Float32Array = npt.NDArray[np.float32]

RAW_EXTENSIONS: frozenset[str] = frozenset(
    {
        ".arw",  # Sony
        ".cr2",  # Canon (CR2)
        ".cr3",  # Canon (CR3)
        ".crw",  # Canon (older)
        ".dng",  # Adobe
        ".nef",  # Nikon
        ".orf",  # Olympus
        ".pef",  # Pentax
        ".raf",  # Fuji (X-Trans soft warning — see PLAN §10)
        ".rw2",  # Panasonic
        ".srw",  # Samsung
    }
)


def is_raw_path(path: Path | str) -> bool:
    """Return True if ``path`` has an extension we route through rawpy."""
    return Path(path).suffix.lower() in RAW_EXTENSIONS


def load_raw(
    path: Path | str,
    *,
    preview: bool = False,
) -> Float32Array:
    """Open a RAW file and return ``(H, W, 3)`` linear-sRGB float32 in ``[0, 1]``."""
    with rawpy.imread(str(path)) as raw:
        rgb = raw.postprocess(
            output_bps=16,
            half_size=preview,
            use_camera_wb=True,
            no_auto_bright=True,
            gamma=(1.0, 1.0),
            output_color=rawpy.ColorSpace.sRGB,
            demosaic_algorithm=rawpy.DemosaicAlgorithm.AHD,
        )
    return (rgb.astype(np.float32) / 65535.0).astype(np.float32)
