"""A tiny scalar fake of the Earth Engine Python API, for testing the REAL mask-building code
in ``maiac_ee.py`` without network access. Each "image" is one pixel: a value and a mask.

Only the operations used by ``pixel_masks`` and ``_Reduction`` are implemented. Semantics
follow Earth Engine: binary operations propagate masks; updateMask keeps a pixel only where
the mask image is unmasked and non-zero; selfMask masks zero values.
"""

from __future__ import annotations

import sys
import types
from typing import Any


class Pix:
    def __init__(self, value: float | int | None, masked: bool = False):
        self.value = value
        self.masked = masked or value is None

    def _bin(self, other: Any, fn: Any) -> Pix:
        o = other if isinstance(other, Pix) else Pix(other)
        if self.masked or o.masked:
            return Pix(0, masked=True)
        return Pix(fn(self.value, o.value))

    def rightShift(self, n: int) -> Pix:
        return self._bin(n, lambda a, b: int(a) >> int(b))

    def bitwiseAnd(self, m: int) -> Pix:
        return self._bin(m, lambda a, b: int(a) & int(b))

    def eq(self, v: Any) -> Pix:
        return self._bin(v, lambda a, b: int(a == b))

    def gte(self, v: Any) -> Pix:
        return self._bin(v, lambda a, b: int(a >= b))

    def lte(self, v: Any) -> Pix:
        return self._bin(v, lambda a, b: int(a <= b))

    def And(self, o: Any) -> Pix:
        return self._bin(o, lambda a, b: int(bool(a) and bool(b)))

    def Or(self, o: Any) -> Pix:
        return self._bin(o, lambda a, b: int(bool(a) or bool(b)))

    def Not(self) -> Pix:
        return Pix(0, True) if self.masked else Pix(int(not self.value))

    def multiply(self, v: Any) -> Pix:
        return self._bin(v, lambda a, b: a * b)

    def add(self, v: Any) -> Pix:
        return self._bin(v, lambda a, b: a + b)

    def updateMask(self, m: Pix) -> Pix:
        keep = not self.masked and not m.masked and bool(m.value)
        return Pix(self.value, masked=not keep)

    def selfMask(self) -> Pix:
        return Pix(self.value, masked=self.masked or not self.value)

    def rename(self, *_: Any) -> Pix:
        return self

    def toFloat(self) -> Pix:
        return self


class Source:
    """A granule with named bands, each a Pix."""

    def __init__(self, **bands: Pix):
        self.bands = bands

    def select(self, name: str) -> Pix:
        return self.bands[name]


class _Image:
    def __new__(cls, x: Any) -> Any:  # ee.Image(x) -> x
        return x

    @staticmethod
    def constant(v: Any) -> Pix:
        return Pix(v)


class FakeReducer:
    def __init__(self, kind: str, unweighted: bool = False):
        self.kind = kind
        self.is_unweighted = unweighted

    def unweighted(self) -> FakeReducer:
        return FakeReducer(self.kind, True)


class _Reducer:
    @staticmethod
    def count() -> FakeReducer:
        return FakeReducer("count")

    @staticmethod
    def sum() -> FakeReducer:
        return FakeReducer("sum")

    @staticmethod
    def mean() -> FakeReducer:
        return FakeReducer("mean")


class RecordingImage:
    """Records reduceRegion calls (for checking the single spatial rule)."""

    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    def reduceRegion(self, **kwargs: Any) -> dict[str, Any]:
        self.calls.append(kwargs)
        return {}


def install() -> types.ModuleType:
    """Install the fake as the `ee` module (call before importing app.datasets.maiac_ee)."""
    module = types.ModuleType("ee")
    module.Image = _Image  # type: ignore[attr-defined]
    module.Reducer = _Reducer  # type: ignore[attr-defined]
    module.Geometry = object  # type: ignore[attr-defined]
    module.Projection = object  # type: ignore[attr-defined]
    module.Dictionary = dict  # type: ignore[attr-defined]
    sys.modules["ee"] = module
    return module
