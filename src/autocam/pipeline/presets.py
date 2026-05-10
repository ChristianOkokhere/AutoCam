"""Export presets — handful of canned ``run_stack → save_image`` configs.

The model can always call ``export_save`` itself for fine control. Presets
are for the human shortcut: "give me the web JPEG version of this".

For now we ship two:

- ``web``   — sRGB JPEG q88, long-edge clamped to 2048 px.
- ``print`` — sRGB JPEG q95, full resolution.

Archival (16-bit TIFF) lives in 9b — Pillow's 16-bit RGB TIFF support is
fragile and we'd rather route through ``tifffile`` once we add it.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import numpy.typing as npt

from autocam.io.image import save_image
from autocam.pipeline.executor import _resize_to_max, run_stack
from autocam.pipeline.stack import EditStack

Float32Array = npt.NDArray[np.float32]


@dataclass(frozen=True)
class Preset:
    name: str
    image_format: str
    quality: int
    long_edge: int  # 0 → no clamp


PRESETS: dict[str, Preset] = {
    "web": Preset(name="web", image_format="jpeg", quality=88, long_edge=2048),
    "print": Preset(name="print", image_format="jpeg", quality=95, long_edge=0),
}


def get_preset(name: str) -> Preset:
    try:
        return PRESETS[name]
    except KeyError as exc:
        known = ", ".join(sorted(PRESETS))
        raise KeyError(f"unknown preset {name!r} — try one of: {known}") from exc


def default_export_path(source: Path | str, preset: str) -> Path:
    """``photo.jpg`` + ``web`` → ``photo_web.jpg`` next to the source."""
    p = Path(source)
    return p.with_name(f"{p.stem}_{preset}.jpg")


def export_with_preset(
    *,
    stack: EditStack,
    source: Path | str | None = None,
    preset: str,
    out_path: Path | str,
) -> Path:
    """Run the stack at full res, apply preset constraints, save to disk."""
    p = get_preset(preset)
    arr = run_stack(stack, source=source, preview=False)
    if p.long_edge > 0:
        arr = _resize_to_max(arr, p.long_edge)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    save_image(arr, out, format=p.image_format, quality=p.quality)
    return out
