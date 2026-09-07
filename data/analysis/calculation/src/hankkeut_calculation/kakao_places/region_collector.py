"""Municipality-wide Kakao category collection using administrative GeoJSON."""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians
from typing import Any

from .client import CATEGORY_GROUPS, KakaoLocalClient
from .models import KakaoPlace

DEFAULT_INITIAL_TILE_METERS = 5_000
DEFAULT_MIN_TILE_METERS = 250

Point = tuple[float, float]
Ring = tuple[Point, ...]
Polygon = tuple[Ring, ...]


@dataclass(frozen=True, slots=True)
class KakaoRegionCategoryCollection:
    region_name: str
    category_group_code: str
    category_group_name: str
    collected_count: int
    searched_tile_count: int
    truncated_tile_count: int
    initial_tile_meters: int
    minimum_tile_meters: int
    address_match_count: int
    address_mismatch_count: int
    address_unverified_count: int
    address_mismatch_samples: tuple[dict[str, str], ...]
    places: tuple[KakaoPlace, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_name": self.region_name,
            "category_group_code": self.category_group_code,
            "category_group_name": self.category_group_name,
            "collected_count": self.collected_count,
            "searched_tile_count": self.searched_tile_count,
            "truncated_tile_count": self.truncated_tile_count,
            "initial_tile_meters": self.initial_tile_meters,
            "minimum_tile_meters": self.minimum_tile_meters,
            "address_match_count": self.address_match_count,
            "address_mismatch_count": self.address_mismatch_count,
            "address_unverified_count": self.address_unverified_count,
            "address_mismatch_samples": list(self.address_mismatch_samples),
            "places": [place.to_dict() for place in self.places],
        }


@dataclass(frozen=True, slots=True)
class KakaoRegionKeywordCollection:
    region_name: str
    query: str
    collected_count: int
    searched_tile_count: int
    truncated_tile_count: int
    initial_tile_meters: int
    minimum_tile_meters: int
    places: tuple[KakaoPlace, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_name": self.region_name,
            "query": self.query,
            "collected_count": self.collected_count,
            "searched_tile_count": self.searched_tile_count,
            "truncated_tile_count": self.truncated_tile_count,
            "initial_tile_meters": self.initial_tile_meters,
            "minimum_tile_meters": self.minimum_tile_meters,
            "places": [place.to_dict() for place in self.places],
        }


class KakaoRegionCollector:
    """Collect and de-duplicate category places inside a municipal boundary.

    The input geometry must be WGS84 (EPSG:4326) Polygon or MultiPolygon.
    Tiles still truncated at the minimum size are reported explicitly so results
    never silently look like a complete count.
    """

    def __init__(self, client: KakaoLocalClient) -> None:
        self._client = client

    def collect_category(
        self,
        *,
        region_name: str,
        geometry: dict[str, Any],
        category_group_code: str,
        initial_tile_meters: int = DEFAULT_INITIAL_TILE_METERS,
        minimum_tile_meters: int = DEFAULT_MIN_TILE_METERS,
    ) -> KakaoRegionCategoryCollection:
        if not region_name.strip():
            raise ValueError("region_name must not be empty.")
        category = category_group_code.strip().upper()
        if category not in CATEGORY_GROUPS:
            raise ValueError("Unsupported category_group_code: " + category_group_code)
        _validate_tile_sizes(initial_tile_meters, minimum_tile_meters)
        polygons = parse_geojson_geometry(geometry)
        bounds = _bounds(polygons)
        tiles = _make_tiles(bounds, initial_tile_meters)
        places_by_id: dict[str, KakaoPlace] = {}
        searched_tile_count = 0
        truncated_tile_count = 0

        while tiles:
            west, south, east, north = tiles.pop()
            result = self._client.collect_category_in_rectangle(
                category_group_code=category,
                west=west,
                south=south,
                east=east,
                north=north,
            )
            searched_tile_count += 1
            if result.result_truncated:
                if _tile_width_meters((west, south, east, north)) > minimum_tile_meters:
                    tiles.extend(_split_tile(west, south, east, north))
                    continue
                truncated_tile_count += 1
            for place in result.places:
                if point_in_multipolygon((place.longitude, place.latitude), polygons):
                    places_by_id[place.place_id] = place

        places = tuple(sorted(places_by_id.values(), key=lambda place: (place.name, place.place_id)))
        matched, mismatched, unverified, samples = _validate_place_addresses(places, region_name)
        return KakaoRegionCategoryCollection(
            region_name=region_name.strip(),
            category_group_code=category,
            category_group_name=CATEGORY_GROUPS[category],
            collected_count=len(places),
            searched_tile_count=searched_tile_count,
            truncated_tile_count=truncated_tile_count,
            initial_tile_meters=initial_tile_meters,
            minimum_tile_meters=minimum_tile_meters,
            address_match_count=matched,
            address_mismatch_count=mismatched,
            address_unverified_count=unverified,
            address_mismatch_samples=samples,
            places=places,
        )

    def collect_keyword(
        self,
        *,
        region_name: str,
        geometry: dict[str, Any],
        query: str,
        initial_tile_meters: int = DEFAULT_INITIAL_TILE_METERS,
        minimum_tile_meters: int = DEFAULT_MIN_TILE_METERS,
    ) -> KakaoRegionKeywordCollection:
        if not region_name.strip() or not query.strip():
            raise ValueError("region_name and query must not be empty.")
        _validate_tile_sizes(initial_tile_meters, minimum_tile_meters)
        polygons = parse_geojson_geometry(geometry)
        tiles = _make_tiles(_bounds(polygons), initial_tile_meters)
        places_by_id: dict[str, KakaoPlace] = {}
        searched_tile_count = truncated_tile_count = 0
        while tiles:
            west, south, east, north = tiles.pop()
            result = self._client.collect_keyword_in_rectangle(
                query=query, west=west, south=south, east=east, north=north
            )
            searched_tile_count += 1
            if result.result_truncated:
                if _tile_width_meters((west, south, east, north)) > minimum_tile_meters:
                    tiles.extend(_split_tile(west, south, east, north))
                    continue
                truncated_tile_count += 1
            for place in result.places:
                if point_in_multipolygon((place.longitude, place.latitude), polygons):
                    places_by_id[place.place_id] = place
        places = tuple(sorted(places_by_id.values(), key=lambda place: (place.name, place.place_id)))
        return KakaoRegionKeywordCollection(
            region_name=region_name.strip(), query=query.strip(), collected_count=len(places),
            searched_tile_count=searched_tile_count, truncated_tile_count=truncated_tile_count,
            initial_tile_meters=initial_tile_meters, minimum_tile_meters=minimum_tile_meters,
            places=places,
        )


def parse_geojson_geometry(geometry: dict[str, Any]) -> tuple[Polygon, ...]:
    """Parse a GeoJSON Polygon/MultiPolygon geometry into validated rings."""
    geometry_type = geometry.get("type") if isinstance(geometry, dict) else None
    coordinates = geometry.get("coordinates") if isinstance(geometry, dict) else None
    if geometry_type == "Polygon":
        return (_parse_polygon(coordinates),)
    if geometry_type == "MultiPolygon" and isinstance(coordinates, list):
        return tuple(_parse_polygon(polygon) for polygon in coordinates)
    raise ValueError("Geometry must be a GeoJSON Polygon or MultiPolygon.")


def point_in_multipolygon(point: Point, polygons: tuple[Polygon, ...]) -> bool:
    return any(_point_in_polygon(point, polygon) for polygon in polygons)


def _parse_polygon(value: Any) -> Polygon:
    if not isinstance(value, list) or not value:
        raise ValueError("GeoJSON polygon must contain at least one ring.")
    rings: list[Ring] = []
    for raw_ring in value:
        if not isinstance(raw_ring, list) or len(raw_ring) < 4:
            raise ValueError("GeoJSON rings must contain at least four coordinates.")
        ring: list[Point] = []
        for raw_point in raw_ring:
            if not isinstance(raw_point, (list, tuple)) or len(raw_point) < 2:
                raise ValueError("GeoJSON coordinates must contain longitude and latitude.")
            longitude, latitude = float(raw_point[0]), float(raw_point[1])
            if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
                raise ValueError("GeoJSON coordinate is out of WGS84 range.")
            ring.append((longitude, latitude))
        rings.append(tuple(ring))
    return tuple(rings)


def _point_in_polygon(point: Point, polygon: Polygon) -> bool:
    if not _point_in_ring(point, polygon[0]):
        return False
    return not any(_point_in_ring(point, hole) for hole in polygon[1:])


def _point_in_ring(point: Point, ring: Ring) -> bool:
    x, y = point
    inside = False
    previous_x, previous_y = ring[-1]
    for current_x, current_y in ring:
        intersects = (current_y > y) != (previous_y > y)
        if intersects:
            boundary_x = (previous_x - current_x) * (y - current_y) / (previous_y - current_y) + current_x
            if x < boundary_x:
                inside = not inside
        previous_x, previous_y = current_x, current_y
    return inside


def _bounds(polygons: tuple[Polygon, ...]) -> tuple[float, float, float, float]:
    points = [point for polygon in polygons for ring in polygon for point in ring]
    longitudes, latitudes = zip(*points, strict=True)
    return min(longitudes), min(latitudes), max(longitudes), max(latitudes)


def _make_tiles(bounds: tuple[float, float, float, float], tile_meters: int) -> list[tuple[float, float, float, float]]:
    west, south, east, north = bounds
    latitude = (south + north) / 2
    lat_step = tile_meters / 111_320
    lon_step = tile_meters / max(111_320 * cos(radians(latitude)), 1)
    tiles: list[tuple[float, float, float, float]] = []
    tile_south = south
    while tile_south < north:
        tile_north = min(tile_south + lat_step, north)
        tile_west = west
        while tile_west < east:
            tile_east = min(tile_west + lon_step, east)
            tiles.append((tile_west, tile_south, tile_east, tile_north))
            tile_west = tile_east
        tile_south = tile_north
    return tiles


def _split_tile(west: float, south: float, east: float, north: float) -> tuple[tuple[float, float, float, float], ...]:
    mid_longitude = (west + east) / 2
    mid_latitude = (south + north) / 2
    return (
        (west, south, mid_longitude, mid_latitude),
        (mid_longitude, south, east, mid_latitude),
        (west, mid_latitude, mid_longitude, north),
        (mid_longitude, mid_latitude, east, north),
    )


def _tile_width_meters(tile: tuple[float, float, float, float]) -> float:
    west, south, east, north = tile
    latitude = (south + north) / 2
    return (east - west) * 111_320 * cos(radians(latitude))


def _validate_tile_sizes(initial_tile_meters: int, minimum_tile_meters: int) -> None:
    if minimum_tile_meters <= 0 or initial_tile_meters < minimum_tile_meters:
        raise ValueError("Tile sizes must satisfy initial_tile_meters >= minimum_tile_meters > 0.")


def _validate_place_addresses(
    places: tuple[KakaoPlace, ...], region_name: str
) -> tuple[int, int, int, tuple[dict[str, str], ...]]:
    matched = mismatched = unverified = 0
    samples: list[dict[str, str]] = []
    expected = region_name.replace(" ", "")
    for place in places:
        address = place.road_address or place.address
        if not address:
            unverified += 1
        elif expected in address.replace(" ", ""):
            matched += 1
        else:
            mismatched += 1
            if len(samples) < 20:
                samples.append({"place_id": place.place_id, "place_name": place.name, "address": address})
    return matched, mismatched, unverified, tuple(samples)
