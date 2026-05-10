"""Op registry — importing this package registers all built-in ops."""

from autocam.ops.base import (
    Float32Array,
    MaskArray,
    MaskOp,
    Op,
    PipelineCtx,
    get_op_class,
    register,
    registered_ops,
)
from autocam.ops.color import SaturationOp, VibranceOp, WhiteBalanceOp
from autocam.ops.curve import RgbCurveOp
from autocam.ops.detail import SharpenOp
from autocam.ops.export_ops import ExportSaveOp
from autocam.ops.geometry import CropOp
from autocam.ops.masks import ColorRangeMaskOp, InvertMaskOp, LuminosityMaskOp
from autocam.ops.tone import (
    BlacksOp,
    ContrastOp,
    ExposureOp,
    HighlightsOp,
    ShadowsOp,
    WhitesOp,
)

__all__ = [
    "BlacksOp",
    "ColorRangeMaskOp",
    "ContrastOp",
    "CropOp",
    "ExportSaveOp",
    "ExposureOp",
    "Float32Array",
    "HighlightsOp",
    "InvertMaskOp",
    "LuminosityMaskOp",
    "MaskArray",
    "MaskOp",
    "Op",
    "PipelineCtx",
    "RgbCurveOp",
    "SaturationOp",
    "ShadowsOp",
    "SharpenOp",
    "VibranceOp",
    "WhiteBalanceOp",
    "WhitesOp",
    "get_op_class",
    "register",
    "registered_ops",
]
