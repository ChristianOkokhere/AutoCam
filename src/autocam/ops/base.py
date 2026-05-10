"""Op base class, registry, and shared pipeline context."""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from dataclasses import dataclass, field, fields
from typing import Any, ClassVar

import numpy as np
import numpy.typing as npt

Float32Array = npt.NDArray[np.float32]


MaskArray = npt.NDArray[np.float32]


@dataclass
class PipelineCtx:
    """Shared state for a single pipeline run.

    ``masks`` is keyed by Op id so adjustment ops can look up a previously
    computed mask via their ``mask`` field. A mask is a ``(H, W)`` float32
    array in ``[0, 1]``; the executor composites adjustments through it.
    """

    source_path: str
    preview: bool = False
    masks: dict[str, MaskArray] = field(default_factory=dict)


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

    ``mask`` is the id of a previously-emitted :class:`MaskOp` whose mask
    the executor should composite this op's effect through. ``None`` (the
    default) applies the op globally.
    """

    name: ClassVar[str] = ""
    id: str = field(default_factory=_new_id)
    mask: str | None = None

    @abstractmethod
    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array: ...

    def describe(self) -> str:
        params = self._params()
        parts = [f"{k}={v}" for k, v in params.items()]
        suffix = f" through mask {self.mask}" if self.mask else ""
        return f"{self.name}({', '.join(parts)}){suffix}"

    def to_dict(self) -> dict[str, Any]:
        d: dict[str, Any] = {"id": self.id, "op": self.name, "params": self._params()}
        if self.mask is not None:
            d["mask"] = self.mask
        return d

    def _params(self) -> dict[str, Any]:
        skip = {"id", "mask"}
        return {f.name: getattr(self, f.name) for f in fields(self) if f.name not in skip}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Op:
        op_cls = get_op_class(data["op"])
        op_id = data.get("id") or _new_id()
        mask = data.get("mask")
        return op_cls(id=op_id, mask=mask, **data.get("params", {}))


@dataclass
class MaskOp(Op):
    """An op whose ``apply`` populates ``ctx.masks`` and returns the buffer.

    Subclasses implement :meth:`compute_mask` to produce a ``(H, W)`` float32
    array in ``[0, 1]``. The default :meth:`apply` stores it in ``ctx.masks``
    keyed by ``self.id`` and returns ``img`` unchanged so the running buffer
    flows through.
    """

    @abstractmethod
    def compute_mask(self, img: Float32Array, ctx: PipelineCtx) -> MaskArray: ...

    def apply(self, img: Float32Array, ctx: PipelineCtx) -> Float32Array:
        ctx.masks[self.id] = self.compute_mask(img, ctx)
        return img
