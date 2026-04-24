"""Edit stack — the append-only list of ops applied to a source image."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from autocam.ops import Op

STACK_VERSION = 1


@dataclass
class EditStack:
    """A replayable, JSON-serializable list of ops applied to ``source``."""

    source: str
    source_hash: str = ""
    ops: list[Op] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    version: int = STACK_VERSION

    def append(self, op: Op) -> None:
        self.ops.append(op)

    def pop(self) -> Op:
        return self.ops.pop()

    def clear(self) -> None:
        self.ops.clear()

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "source": self.source,
            "source_hash": self.source_hash,
            "created_at": self.created_at,
            "ops": [op.to_dict() for op in self.ops],
        }

    def to_json(self, **kwargs: Any) -> str:
        return json.dumps(self.to_dict(), **kwargs)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EditStack:
        version = data.get("version")
        if version != STACK_VERSION:
            raise ValueError(f"Unsupported stack version: {version!r} (expected {STACK_VERSION})")
        ops = [Op.from_dict(o) for o in data.get("ops", [])]
        return cls(
            source=data["source"],
            source_hash=data.get("source_hash", ""),
            ops=ops,
            created_at=data.get("created_at", datetime.now(UTC).isoformat()),
            version=STACK_VERSION,
        )

    @classmethod
    def from_json(cls, text: str) -> EditStack:
        return cls.from_dict(json.loads(text))

    @classmethod
    def load(cls, path: Path | str) -> EditStack:
        return cls.from_json(Path(path).read_text())

    def save(self, path: Path | str) -> None:
        Path(path).write_text(self.to_json(indent=2))


def source_hash(path: Path | str, *, max_bytes: int = 1_000_000) -> str:
    """Fast identity hash over the first ``max_bytes`` of a file."""
    h = hashlib.sha256()
    with Path(path).open("rb") as f:
        h.update(f.read(max_bytes))
    return "sha256:" + h.hexdigest()[:16]
