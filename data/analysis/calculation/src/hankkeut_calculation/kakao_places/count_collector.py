"""Low-call municipality counting: metadata for interiors, details at boundaries."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .client import CATEGORY_GROUPS, KakaoLocalClient
from .region_collector import (
    DEFAULT_MIN_TILE_METERS,
    _bounds,
    _make_tiles,
    _split_tile,
    _tile_width_meters,
    _validate_place_addresses,
    parse_geojson_geometry,
    point_in_multipolygon,
)

DEFAULT_COUNT_TILE_METERS = 10_000
DEFAULT_DENSE_TILE_THRESHOLD = 675


@dataclass(frozen=True, slots=True)
class KakaoRegionCountCollection:
    region_name: str
    category_group_code: str
    category_group_name: str
    collected_count: int
    interior_metadata_count: int
    boundary_verified_count: int
    metadata_request_count: int
    detail_request_tile_count: int
    initial_tile_meters: int
    minimum_tile_meters: int
    dense_tile_threshold: int
    address_match_count: int
    address_mismatch_count: int
    address_unverified_count: int
    address_mismatch_samples: tuple[dict[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in self.__dataclass_fields__}


class KakaoRegionCountCollector:
    def __init__(self, client: KakaoLocalClient) -> None:
        self._client = client

    def collect_category(
        self, *, region_name: str, geometry: dict[str, Any], category_group_code: str,
        initial_tile_meters: int = DEFAULT_COUNT_TILE_METERS,
        minimum_tile_meters: int = DEFAULT_MIN_TILE_METERS,
        dense_tile_threshold: int = DEFAULT_DENSE_TILE_THRESHOLD,
    ) -> KakaoRegionCountCollection:
        category = category_group_code.strip().upper()
        if category not in CATEGORY_GROUPS:
            raise ValueError("Unsupported category_group_code: " + category_group_code)
        if initial_tile_meters < minimum_tile_meters or minimum_tile_meters <= 0:
            raise ValueError("Tile sizes must satisfy initial >= minimum > 0.")
        polygons = parse_geojson_geometry(geometry)
        tiles = _make_tiles(_bounds(polygons), initial_tile_meters)
        interior_count = boundary_count = metadata_requests = detail_tiles = 0
        boundary_places = {}
        while tiles:
            tile = tiles.pop()
            west, south, east, north = tile
            metadata = self._client.inspect_category_in_rectangle(
                category_group_code=category, west=west, south=south, east=east, north=north
            )
            metadata_requests += 1
            if metadata.total_count > dense_tile_threshold and _tile_width_meters(tile) > minimum_tile_meters:
                tiles.extend(_split_tile(*tile))
                continue
            if _tile_is_safely_inside(tile, polygons):
                interior_count += metadata.total_count
                continue
            details = self._client.collect_category_in_rectangle(
                category_group_code=category, west=west, south=south, east=east, north=north
            )
            detail_tiles += 1
            for place in details.places:
                if point_in_multipolygon((place.longitude, place.latitude), polygons):
                    boundary_places[place.place_id] = place
        places = tuple(boundary_places.values())
        matched, mismatched, unverified, samples = _validate_place_addresses(places, region_name)
        boundary_count = len(places)
        return KakaoRegionCountCollection(
            region_name=region_name, category_group_code=category, category_group_name=CATEGORY_GROUPS[category],
            collected_count=interior_count + boundary_count, interior_metadata_count=interior_count,
            boundary_verified_count=boundary_count, metadata_request_count=metadata_requests,
            detail_request_tile_count=detail_tiles, initial_tile_meters=initial_tile_meters,
            minimum_tile_meters=minimum_tile_meters, dense_tile_threshold=dense_tile_threshold,
            address_match_count=matched, address_mismatch_count=mismatched,
            address_unverified_count=unverified, address_mismatch_samples=samples,
        )


def _tile_is_safely_inside(tile: tuple[float, float, float, float], polygons: Any) -> bool:
    west, south, east, north = tile
    corners = ((west, south), (west, north), (east, south), (east, north))
    if not all(point_in_multipolygon(corner, polygons) for corner in corners):
        return False
    # A boundary vertex inside the rectangle means the tile may contain a hole or
    # boundary segment, so use detailed place filtering instead of metadata.
    return not any(west <= x <= east and south <= y <= north for polygon in polygons for ring in polygon for x, y in ring)
