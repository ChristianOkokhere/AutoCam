"""Tests for export presets."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from autocam.ops.tone import ExposureOp
from autocam.pipeline.color import linear_to_srgb
from autocam.pipeline.presets import (
    PRESETS,
    default_export_path,
    export_with_preset,
    get_preset,
)
from autocam.pipeline.stack import EditStack


def _write_jpeg(path: Path, *, value: float = 0.5, size: tuple[int, int]) -> Path:
    arr = np.full((size[1], size[0], 3), value, dtype=np.float32)
    display = linear_to_srgb(arr)
    arr8 = np.clip(display * 255.0, 0, 255).astype(np.uint8)
    Image.fromarray(arr8).save(path, quality=95)
    return path


def test_get_preset_known() -> None:
    p = get_preset("web")
    assert p.name == "web"
    assert p.image_format == "jpeg"
    assert p.long_edge == 2048


def test_get_preset_unknown_raises() -> None:
    with pytest.raises(KeyError, match="unknown preset"):
        get_preset("archival")  # not shipped in 9a


def test_default_export_path_appends_preset_to_stem() -> None:
    out = default_export_path(Path("/tmp/photo.arw"), "web")
    assert out == Path("/tmp/photo_web.jpg")


def test_export_web_clamps_long_edge_to_2048(tmp_path: Path) -> None:
    src = _write_jpeg(tmp_path / "src.jpg", size=(4000, 3000))
    stack = EditStack(source=str(src))
    stack.append(ExposureOp(ev=0.0))

    out = tmp_path / "out_web.jpg"
    export_with_preset(stack=stack, preset="web", out_path=out)

    with Image.open(out) as im:
        # 4000 → 2048 (cap), 3000 → round(3000 * 2048/4000) = 1536.
        assert max(im.size) == 2048
        assert im.size == (2048, 1536)


def test_export_print_keeps_full_resolution(tmp_path: Path) -> None:
    src = _write_jpeg(tmp_path / "src.jpg", size=(3000, 2000))
    stack = EditStack(source=str(src))

    out = tmp_path / "out_print.jpg"
    export_with_preset(stack=stack, preset="print", out_path=out)

    with Image.open(out) as im:
        assert im.size == (3000, 2000)


def test_export_creates_parent_dir(tmp_path: Path) -> None:
    src = _write_jpeg(tmp_path / "src.jpg", size=(800, 600))
    stack = EditStack(source=str(src))

    nested = tmp_path / "deep" / "nested" / "out.jpg"
    export_with_preset(stack=stack, preset="web", out_path=nested)
    assert nested.exists()


def test_presets_dict_keys_match_dataclass_names() -> None:
    for name, preset in PRESETS.items():
        assert name == preset.name


def test_cli_export_writes_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    from autocam.cli import main

    src = _write_jpeg(tmp_path / "src.jpg", size=(800, 600))
    stack_path = tmp_path / "stack.json"
    s = EditStack(source=str(src))
    s.append(ExposureOp(ev=0.3))
    s.save(stack_path)
    out = tmp_path / "src_web.jpg"

    code = main(
        [
            "export",
            "web",
            "--stack",
            str(stack_path),
            "--in",
            str(src),
            "--out",
            str(out),
        ]
    )
    captured = capsys.readouterr()
    assert code == 0
    assert "wrote" in captured.out
    assert out.exists()
