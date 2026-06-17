from __future__ import annotations

from packages.geo.bc_gate import BC_BBOX


def parse_bbox(raw: str | None) -> list[float]:
    if not raw:
        return list(BC_BBOX)
    parts = [float(part.strip()) for part in raw.split(",")]
    if len(parts) != 4:
        raise ValueError("bbox must be min_lng,min_lat,max_lng,max_lat")
    min_lng, min_lat, max_lng, max_lat = parts
    bc_min_lng, bc_min_lat, bc_max_lng, bc_max_lat = BC_BBOX
    clamped = [
        max(min_lng, bc_min_lng),
        max(min_lat, bc_min_lat),
        min(max_lng, bc_max_lng),
        min(max_lat, bc_max_lat),
    ]
    if clamped[0] > clamped[2] or clamped[1] > clamped[3]:
        raise ValueError("bbox does not intersect Metro Vancouver bounds")
    return clamped
