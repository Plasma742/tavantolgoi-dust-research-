"""Server-side tile proxy for Earth Engine map layers.

The browser never receives Earth Engine URLs or credentials. When a layer is built the
backend registers each EE ``TileFetcher`` under a random 192-bit id and returns
``/api/tiles/{id}/{z}/{x}/{y}.png``. Tiles outside the ROI bounding box are answered
with a transparent tile without calling Earth Engine (quota protection).

Token lifecycle: ids live in process memory only and expire after ``ttl_s`` (or on restart);
they are bearer tokens for one rendered image. In public mode each id is bound to the
principal that created it, and other principals get the same answer as for an unknown id.
The tile byte cache is per id, so it never crosses principals.
"""

from __future__ import annotations

import math
import secrets
import struct
import threading
import zlib
from dataclasses import dataclass
from typing import Any, Protocol

from cachetools import LRUCache, TTLCache

from .errors import ApiError, TileExpired


class TileFetcherLike(Protocol):
    def fetch_tile(self, x: float, y: float, z: float) -> Any: ...


def _png_transparent(size: int = 256) -> bytes:
    def chunk(kind: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xFFFFFFFF)

    raw = b"".join(b"\x00" + b"\x00\x00\x00\x00" * size for _ in range(size))
    ihdr = struct.pack(">IIBBBBB", size, size, 8, 6, 0, 0, 0)
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 9)) + chunk(b"IEND", b"")


TRANSPARENT_PNG = _png_transparent()


def tile_bounds(z: int, x: int, y: int) -> tuple[float, float, float, float]:
    n = 2**z
    west = x / n * 360.0 - 180.0
    east = (x + 1) / n * 360.0 - 180.0
    north = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * y / n))))
    south = math.degrees(math.atan(math.sinh(math.pi * (1 - 2 * (y + 1) / n))))
    return west, south, east, north


def _intersects(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


@dataclass
class _Entry:
    fetcher: TileFetcherLike
    bbox: tuple[float, float, float, float]
    owner: str | None


class TileRegistry:
    def __init__(self, ttl_s: int, max_zoom: int, max_layers: int = 512, max_tiles: int = 2_000):
        self._layers: TTLCache[str, _Entry] = TTLCache(maxsize=max_layers, ttl=ttl_s)
        self._tiles: LRUCache[tuple[str, int, int, int], bytes] = LRUCache(maxsize=max_tiles)
        self._lock = threading.Lock()
        self.max_zoom = max_zoom

    def register(
        self, fetcher: TileFetcherLike, bbox: tuple[float, float, float, float], owner: str | None = None
    ) -> str:
        tile_id = secrets.token_urlsafe(24)
        with self._lock:
            self._layers[tile_id] = _Entry(fetcher, bbox, owner)
        return tile_id

    def get_tile(self, tile_id: str, z: int, x: int, y: int, requester: str | None = None) -> tuple[bytes, bool]:
        """Return (png_bytes, came_from_earth_engine)."""
        if not (0 <= z <= self.max_zoom):
            raise ApiError(f"Zoom must be between 0 and {self.max_zoom}.", code="INVALID_TILE")
        n = 2**z
        if not (0 <= x < n and 0 <= y < n):
            raise ApiError("Tile coordinates out of range.", code="INVALID_TILE")
        with self._lock:
            entry = self._layers.get(tile_id)
            cached = self._tiles.get((tile_id, z, x, y))
        if entry is None or (entry.owner is not None and entry.owner != requester):
            raise TileExpired("Map layer expired or unknown. Reload the layer.")
        if cached is not None:
            return cached, False
        if not _intersects(tile_bounds(z, x, y), entry.bbox):
            return TRANSPARENT_PNG, False
        data = entry.fetcher.fetch_tile(x=x, y=y, z=z)
        png = bytes(data)
        with self._lock:
            self._tiles[(tile_id, z, x, y)] = png
        return png, True
