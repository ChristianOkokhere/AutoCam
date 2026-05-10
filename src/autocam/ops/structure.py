"""Structure / compositing ops — resize, pad, border, text, watermark.

These ops change the canvas (resize / pad / border) or paint onto it (text /
watermark). They convert to display-gamma sRGB locally so Pillow can do the
heavy lifting in 8-bit, then convert back to the linear-sRGB float32 buffer
the rest of the pipeline speaks.

Colour parsing accepts ``#rrggbb`` / ``#rrggbbaa`` / Pillow named colours
(``"white"``, ``"#fff"``, ``"rgb(255, 200, 0)"``).
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import ClassVar, Literal

import numpy as np
from PIL import Image, ImageColor, ImageDraw, ImageFont

from autocam.ops.base import Float32Array, Op, PipelineCtx, register
from autocam.pipeline.color import linear_to_srgb, srgb_to_linear

ResizeMode = Literal["lanczos", "bilinear", "nearest"]
Anchor = Literal[
    "tl",
    "tc",
    "tr",
    "ml",
    "mc",
    "mr",
    "bl",
    "bc",
    "br",
]


_RESIZE_FILTERS = {
    "lanczos": Image.LANCZOS,
    "bilinear": Image.BILINEAR,
    "nearest": Image.NEAREST,
}


def _parse_color(spec: str) -> tuple[int, int, int, int]:
    """Return ``(r, g, b, a)`` 0..255 from any Pillow-acceptable colour string."""
    rgba = ImageColor.getcolor(spec, "RGBA")
    if isinstance(rgba, tuple) and len(rgba) == 4:
        return rgba
    if isinstance(rgba, tuple) and len(rgba) == 3:
        r, g, b = rgba
        return (r, g, b, 255)
    raise ValueError(f"unsupported color: {spec!r}")


def _to_pil_uint8(img: Float32Array) -> Image.Image:
    display = linear_to_srgb(img)
    arr8 = np.ascontiguousarray(np.clip(display * 255.0, 0, 255).astype(np.uint8))
    return Image.fromarray(arr8, mode="RGB")


def _from_pil(pil: Image.Image) -> Float32Array:
    if pil.mode != "RGB":
        pil = pil.convert("RGB")
    arr = np.asarray(pil, dtype=np.float32) / 255.0
    return srgb_to_linear(arr)


def _anchor_xy(
    canvas_w: int, canvas_h: int, item_w: int, item_h: int, anchor: Anchor, x_off: int, y_off: int
) -> tuple[int, int]:
    """Top-left corner for an item of ``item_w x item_h`` placed by ``anchor``.

    ``x_off`` / ``y_off`` are pixel offsets *inwards* from the anchor edge.
    """
    if anchor[0] == "t":
        y = y_off
    elif anchor[0] == "b":
        y = canvas_h - item_h - y_off
    else:
        y = (canvas_h - item_h) // 2 + y_off

    if anchor[1] == "l":
        x = x_off
    elif anchor[1] == "r":
        x = canvas_w - item_w - x_off
    else:
        x = (canvas_w - item_w) // 2 + x_off
    return x, y


@register
@dataclass
class ResizeOp(Op):
    """Resize the buffer. Provide *one* of ``scale`` / ``width`` / ``height``."""

    name: ClassVar[str] = "struct.resize"
    scale: float = 0.0
    width: int = 0
    height: int = 0
    mode: ResizeMode = "lanczos"

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        h, w = img.shape[:2]
        if self.scale > 0.0:
            new_w, new_h = max(1, round(w * self.scale)), max(1, round(h * self.scale))
        elif self.width > 0:
            new_w = int(self.width)
            new_h = max(1, round(h * (new_w / w)))
        elif self.height > 0:
            new_h = int(self.height)
            new_w = max(1, round(w * (new_h / h)))
        else:
            raise ValueError("struct.resize needs scale, width, or height")
        if new_w == w and new_h == h:
            return img
        pil = _to_pil_uint8(img).resize((new_w, new_h), _RESIZE_FILTERS[self.mode])
        return _from_pil(pil)


@register
@dataclass
class PadOp(Op):
    """Add solid-colour padding around the image. Pixel counts."""

    name: ClassVar[str] = "struct.pad"
    top: int = 0
    right: int = 0
    bottom: int = 0
    left: int = 0
    color: str = "#ffffff"

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        if all(v == 0 for v in (self.top, self.right, self.bottom, self.left)):
            return img
        rgba = _parse_color(self.color)
        h, w = img.shape[:2]
        canvas_w = w + self.left + self.right
        canvas_h = h + self.top + self.bottom
        canvas = Image.new("RGB", (canvas_w, canvas_h), rgba[:3])
        canvas.paste(_to_pil_uint8(img), (self.left, self.top))
        return _from_pil(canvas)


@register
@dataclass
class BorderOp(Op):
    """Outer border whose width is a percentage of the *short* edge."""

    name: ClassVar[str] = "struct.border"
    width_pct: float = 2.0
    color: str = "#ffffff"

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        if self.width_pct <= 0.0:
            return img
        h, w = img.shape[:2]
        edge = min(h, w)
        px = max(1, round(edge * self.width_pct / 100.0))
        rgba = _parse_color(self.color)
        canvas = Image.new("RGB", (w + px * 2, h + px * 2), rgba[:3])
        canvas.paste(_to_pil_uint8(img), (px, px))
        return _from_pil(canvas)


@register
@dataclass
class TextOp(Op):
    """Draw ``content`` onto the canvas.

    ``size`` is in pixels. ``font_path`` (optional) is a TTF/OTF file; without
    it we use Pillow's bundled default. ``anchor`` is two chars
    (``t``/``m``/``b`` row, ``l``/``c``/``r`` column). ``x_off`` / ``y_off``
    are pixel offsets *inwards* from that anchor.
    """

    name: ClassVar[str] = "struct.text"
    content: str = ""
    size: int = 24
    color: str = "#ffffff"
    anchor: Anchor = "br"
    x_off: int = 16
    y_off: int = 16
    font_path: str = ""

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        if not self.content:
            return img
        rgba = _parse_color(self.color)
        font = _load_font(self.font_path, self.size)
        pil = _to_pil_uint8(img).convert("RGBA")
        layer = Image.new("RGBA", pil.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)

        # Pillow's textbbox gives a tight bounding box for placement.
        bbox = draw.textbbox((0, 0), self.content, font=font)
        text_w = bbox[2] - bbox[0]
        text_h = bbox[3] - bbox[1]
        x, y = _anchor_xy(
            pil.size[0], pil.size[1], text_w, text_h, self.anchor, self.x_off, self.y_off
        )
        # textbbox includes the negative offset of the glyph origin; correct it.
        draw.text((x - bbox[0], y - bbox[1]), self.content, fill=rgba, font=font)

        composited = Image.alpha_composite(pil, layer).convert("RGB")
        return _from_pil(composited)


@register
@dataclass
class WatermarkOp(Op):
    """Alpha-composite an image (PNG / TIFF / JPEG) onto the canvas.

    ``path`` is read from disk each apply. ``scale_pct`` resizes the watermark
    relative to the canvas's *short* edge before placement (e.g. ``20.0``
    makes the watermark's long edge 20 % of the short edge of the photo).
    """

    name: ClassVar[str] = "struct.watermark"
    path: str = ""
    scale_pct: float = 20.0
    opacity: float = 0.8
    anchor: Anchor = "br"
    x_off: int = 16
    y_off: int = 16

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        if not self.path:
            raise ValueError("struct.watermark requires a `path`")
        wm_path = Path(self.path).expanduser()
        with Image.open(wm_path) as raw:
            wm = raw.convert("RGBA")

        canvas = _to_pil_uint8(img).convert("RGBA")
        canvas_w, canvas_h = canvas.size
        if self.scale_pct > 0.0:
            short = min(canvas_w, canvas_h)
            target_long = max(1, round(short * self.scale_pct / 100.0))
            wm_w, wm_h = wm.size
            wm_scale = target_long / max(wm_w, wm_h)
            wm = wm.resize(
                (max(1, round(wm_w * wm_scale)), max(1, round(wm_h * wm_scale))),
                Image.LANCZOS,
            )

        if self.opacity < 1.0:
            wm = _multiply_alpha(wm, max(0.0, min(1.0, self.opacity)))

        x, y = _anchor_xy(
            canvas_w, canvas_h, wm.size[0], wm.size[1], self.anchor, self.x_off, self.y_off
        )
        layer = Image.new("RGBA", canvas.size, (0, 0, 0, 0))
        layer.paste(wm, (x, y), wm)
        composited = Image.alpha_composite(canvas, layer).convert("RGB")
        return _from_pil(composited)


def _load_font(font_path: str, size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    if font_path:
        return ImageFont.truetype(font_path, size=size)
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        # Pillow < 10.1: load_default() takes no args; falls back to bitmap.
        return ImageFont.load_default()


def _multiply_alpha(rgba: Image.Image, opacity: float) -> Image.Image:
    r, g, b, a = rgba.split()
    a = a.point(lambda v: int(v * opacity))
    return Image.merge("RGBA", (r, g, b, a))
