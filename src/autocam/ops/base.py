"""Op base class, registry, and shared pipeline context."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields
from typing import Any, ClassVar

import numpy as np
import numpy.typing as npt

Float32Array = npt.NDArray[np.float32]


@dataclass
class PipelineCtx:
    """Shared state for a single pipeline run."""

    source_path: str
    preview: bool = False


_REGISTRY: dict[str, type[Op]] = {}


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


def register(cls: type[Op]) -> type[Op]:
    """Register an Op subclass by its ``name``."""
    if not cls.name:
        raise ValueError(f"{cls.__name__} is missing a `name` ClassVar")
    _REGISTRY[cls.name] = cls
    return cls


def get_op_class(name: str) -> type[Op]:
    try:
        return _REGISTRY[name]
    except KeyError as exc:
        raise KeyError(f"Unknown op: {name!r}") from exc


def registered_ops() -> dict[str, type[Op]]:
    return dict(_REGISTRY)


@dataclass
class Op(ABC):
    """Abstract base for pipeline ops.

    Subclasses are ``@dataclass``es that set a ``name`` ClassVar and
    implement ``apply``. ``to_dict`` / ``from_dict`` round-trip through JSON.
    """

    name: ClassVar[str] = ""
    id: str = field(default_factory=_new_id)

    @abstractmethod
    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array: ...

    def describe(self) -> str:
        params = {k: v for k, v in self._params().items()}
        parts = [f"{k}={v}" for k, v in params.items()]
        return f"{self.name}({', '.join(parts)})"

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "op": self.name, "params": self._params()}

    def _params(self) -> dict[str, Any]:
        return {f.name: getattr(self, f.name) for f in fields(self) if f.name != "id"}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Op:
        op_cls = get_op_class(data["op"])
        op_id = data.get("id") or _new_id()
        return op_cls(id=op_id, **data.get("params", {}))
