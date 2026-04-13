"""Pure-python point-in-polygon using ray-casting algorithm."""

from __future__ import annotations


def point_in_polygon(
    px: float, py: float, polygon: list[tuple[float, float]]
) -> bool:
    """Test if a point (px, py) is inside a polygon.

    Uses the ray-casting algorithm. The polygon is a list of
    (x, y) coordinate tuples forming a closed ring. Works with
    both convex and concave polygons.

    Args:
        px: Point x coordinate (longitude)
        py: Point y coordinate (latitude)
        polygon: List of (longitude, latitude) tuples

    Returns:
        True if the point is inside the polygon.
    """
    n = len(polygon)
    if n < 3:
        return False

    inside = False
    j = n - 1

    for i in range(n):
        xi, yi = polygon[i]
        xj, yj = polygon[j]

        if ((yi > py) != (yj > py)) and (
            px < (xj - xi) * (py - yi) / (yj - yi) + xi
        ):
            inside = not inside
        j = i

    return inside


def point_in_multipolygon(
    px: float, py: float, multipolygon: list[list[tuple[float, float]]]
) -> bool:
    """Test if a point is inside any polygon of a multipolygon."""
    return any(point_in_polygon(px, py, poly) for poly in multipolygon)
