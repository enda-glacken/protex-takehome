"""Zone geometry. Zones are named polygons in normalised (0..1) frame coordinates."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

Point = Tuple[float, float]


@dataclass
class Zone:
    id: str
    name: str
    kind: str  # belt | work | staging | other
    polygon: List[Point]

    def contains(self, p: Point) -> bool:
        return point_in_polygon(p, self.polygon)


def point_in_polygon(p: Point, poly: Sequence[Point]) -> bool:
    """Ray casting. Good enough for the handful of small polygons we have."""
    x, y = p
    inside = False
    n = len(poly)
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            inside = not inside
    return inside


def load_zones(path: Path | str) -> List[Zone]:
    raw = json.loads(Path(path).read_text())
    return [Zone(z["id"], z.get("name", z["id"]), z.get("kind", "other"),
                 [(float(x), float(y)) for x, y in z["polygon"]]) for z in raw["zones"]]


def zone_for(p: Point, zones: Sequence[Zone], kinds: Optional[Sequence[str]] = None) -> Optional[Zone]:
    for z in zones:
        if (kinds is None or z.kind in kinds) and z.contains(p):
            return z
    return None
