from __future__ import annotations

import heapq
import math
import json
import urllib.request
from dataclasses import dataclass


@dataclass(frozen=True)
class LatLng:
    lat: float
    lng: float


def _clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def _euclid(a: tuple[int, int], b: tuple[int, int]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def astar_grid_route(start: LatLng, goal: LatLng, grid_size: int = 80) -> list[LatLng]:
    grid_size = int(_clamp(grid_size, 20, 220))

    lat_min = min(start.lat, goal.lat)
    lat_max = max(start.lat, goal.lat)
    lng_min = min(start.lng, goal.lng)
    lng_max = max(start.lng, goal.lng)

    lat_margin = max((lat_max - lat_min) * 0.15, 0.002)
    lng_margin = max((lng_max - lng_min) * 0.15, 0.002)
    lat_min -= lat_margin
    lat_max += lat_margin
    lng_min -= lng_margin
    lng_max += lng_margin

    def to_grid(p: LatLng) -> tuple[int, int]:
        i = int(round((p.lat - lat_min) / (lat_max - lat_min) * (grid_size - 1)))
        j = int(round((p.lng - lng_min) / (lng_max - lng_min) * (grid_size - 1)))
        return (
            int(_clamp(i, 0, grid_size - 1)),
            int(_clamp(j, 0, grid_size - 1)),
        )

    def to_latlng(node: tuple[int, int]) -> LatLng:
        i, j = node
        lat = lat_min + (i / (grid_size - 1)) * (lat_max - lat_min)
        lng = lng_min + (j / (grid_size - 1)) * (lng_max - lng_min)
        return LatLng(lat=lat, lng=lng)

    start_n = to_grid(start)
    goal_n = to_grid(goal)

    if start_n == goal_n:
        return [start, goal]

    neighbors = [
        (-1, 0, 1.0),
        (1, 0, 1.0),
        (0, -1, 1.0),
        (0, 1, 1.0),
        (-1, -1, math.sqrt(2)),
        (-1, 1, math.sqrt(2)),
        (1, -1, math.sqrt(2)),
        (1, 1, math.sqrt(2)),
    ]

    open_heap: list[tuple[float, tuple[int, int]]] = []
    heapq.heappush(open_heap, (0.0, start_n))
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], float] = {start_n: 0.0}

    closed: set[tuple[int, int]] = set()
    while open_heap:
        _, current = heapq.heappop(open_heap)
        if current in closed:
            continue
        if current == goal_n:
            path = [current]
            while current in came_from:
                current = came_from[current]
                path.append(current)
            path.reverse()
            pts = [to_latlng(n) for n in path]
            pts[0] = start
            pts[-1] = goal
            return pts

        closed.add(current)
        ci, cj = current
        for di, dj, cost in neighbors:
            ni, nj = ci + di, cj + dj
            if ni < 0 or nj < 0 or ni >= grid_size or nj >= grid_size:
                continue
            nxt = (ni, nj)
            tentative = g_score[current] + cost
            if tentative < g_score.get(nxt, float("inf")):
                came_from[nxt] = current
                g_score[nxt] = tentative
                f = tentative + _euclid(nxt, goal_n)
                heapq.heappush(open_heap, (f, nxt))

    return [start, goal]


def osrm_route(
    start: LatLng, goal: LatLng, osrm_base_url: str = "https://router.project-osrm.org"
) -> tuple[list[LatLng], float | None, float | None] | None:
    """
    Fetch a road-accurate route polyline from the free public OSRM server.
    Returns list[LatLng] or None on failure.
    """
    try:
        base = (osrm_base_url or "").rstrip("/")
        url = (
            f"{base}/route/v1/driving/"
            f"{start.lng:.6f},{start.lat:.6f};{goal.lng:.6f},{goal.lat:.6f}"
            f"?overview=full&geometries=geojson&steps=false"
        )
        req = urllib.request.Request(url, headers={"User-Agent": "QuickEatsDemo/1.0"})
        with urllib.request.urlopen(req, timeout=6) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
        routes = payload.get("routes") or []
        if not routes:
            return None
        geom = routes[0].get("geometry") or {}
        coords = geom.get("coordinates") or []
        if len(coords) < 2:
            return None
        points = [LatLng(lat=float(lat), lng=float(lng)) for lng, lat in coords]
        distance_m = routes[0].get("distance")
        duration_s = routes[0].get("duration")
        return points, (float(distance_m) if distance_m is not None else None), (float(duration_s) if duration_s is not None else None)
    except Exception:
        return None


def best_route(
    start: LatLng, goal: LatLng, grid_size: int = 80, osrm_base_url: str | None = None
) -> tuple[str, list[LatLng], dict]:
    """
    Prefer real road routing (OSRM). Fallback to A* grid.
    Returns (source, points) where source in {'osrm','astar'}.
    """
    if osrm_base_url:
        got = osrm_route(start, goal, osrm_base_url=osrm_base_url)
        if got:
            pts, dist, dur = got
            return "osrm", pts, {"distance_m": dist, "duration_s": dur}
    got = osrm_route(start, goal)
    if got:
        pts, dist, dur = got
        return "osrm", pts, {"distance_m": dist, "duration_s": dur}
    return "astar", astar_grid_route(start, goal, grid_size=grid_size), {"distance_m": None, "duration_s": None}
