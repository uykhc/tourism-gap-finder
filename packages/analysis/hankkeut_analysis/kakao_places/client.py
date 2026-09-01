"""Small dependency-free client for Kakao Local category search."""

from __future__ import annotations

import json
import math
from collections.abc import Callable, Iterable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .models import KakaoCategoryCollection, KakaoCategoryMetadata, KakaoKeywordCollection, KakaoPlace

DEFAULT_BASE_URL = "https://dapi.kakao.com/v2/local/search/category.json"
KEYWORD_SEARCH_BASE_URL = "https://dapi.kakao.com/v2/local/search/keyword.json"
MAX_RADIUS_METERS = 20_000
MAX_PAGE_SIZE = 15
MAX_PAGES = 45

CATEGORY_GROUPS: dict[str, str] = {
    "CT1": "문화시설",
    "AT4": "관광명소",
    "AD5": "숙박",
    "FD6": "음식점",
    "CE7": "카페",
    "PK6": "주차장",
    "SW8": "지하철역",
    "PO3": "공공기관",
}


class KakaoLocalApiError(RuntimeError):
    """Raised when Kakao Local API cannot provide a valid response."""


class KakaoLocalClient:
    def __init__(
        self,
        rest_api_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        timeout_seconds: float = 20.0,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        if not rest_api_key.strip():
            raise ValueError("Kakao REST API key must not be empty.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero.")
        self._rest_api_key = rest_api_key.strip()
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds
        self._opener = opener

    def collect_category_nearby(
        self,
        *,
        category_group_code: str,
        longitude: float,
        latitude: float,
        radius_meters: int = 2_000,
    ) -> KakaoCategoryCollection:
        category = _validate_category(category_group_code)
        _validate_coordinates(longitude, latitude)
        if not 0 <= radius_meters <= MAX_RADIUS_METERS:
            raise ValueError(f"radius_meters must be between 0 and {MAX_RADIUS_METERS}.")

        places_by_id: dict[str, KakaoPlace] = {}
        total_count = 0
        pageable_count = 0
        page = 1
        while True:
            payload = self._request_page(
                category_group_code=category,
                x=longitude,
                y=latitude,
                radius=radius_meters,
                page=page,
            )
            meta = payload.get("meta")
            documents = payload.get("documents")
            if not isinstance(meta, dict) or not isinstance(documents, list):
                raise KakaoLocalApiError("Kakao Local API response has an invalid shape.")
            total_count = _non_negative_int(meta.get("total_count"), "total_count")
            pageable_count = _non_negative_int(meta.get("pageable_count"), "pageable_count")
            for document in documents:
                if isinstance(document, dict):
                    place = _to_place(document)
                    places_by_id[place.place_id] = place
            if bool(meta.get("is_end")) or page >= MAX_PAGES:
                break
            page += 1

        places = tuple(sorted(places_by_id.values(), key=lambda item: (item.distance_meters is None, item.distance_meters, item.name)))
        return KakaoCategoryCollection(
            category_group_code=category,
            category_group_name=CATEGORY_GROUPS[category],
            center_longitude=longitude,
            center_latitude=latitude,
            radius_meters=radius_meters,
            api_total_count=total_count,
            pageable_count=pageable_count,
            collected_count=len(places),
            result_truncated=total_count > pageable_count or len(places) < min(total_count, pageable_count),
            places=places,
        )

    def collect_category_in_rectangle(
        self,
        *,
        category_group_code: str,
        west: float,
        south: float,
        east: float,
        north: float,
    ) -> KakaoCategoryCollection:
        """Collect one category from a WGS84 bounding rectangle.

        Kakao caps pagination at 45 pages.  Callers collecting an entire
        municipality must subdivide a result whose ``result_truncated`` is true.
        """
        category = _validate_category(category_group_code)
        _validate_rectangle(west, south, east, north)
        places_by_id: dict[str, KakaoPlace] = {}
        total_count = 0
        pageable_count = 0
        page = 1
        while True:
            payload = self._request_page(
                category_group_code=category,
                rect=f"{west},{south},{east},{north}",
                page=page,
            )
            meta = payload.get("meta")
            documents = payload.get("documents")
            if not isinstance(meta, dict) or not isinstance(documents, list):
                raise KakaoLocalApiError("Kakao Local API response has an invalid shape.")
            total_count = _non_negative_int(meta.get("total_count"), "total_count")
            pageable_count = _non_negative_int(meta.get("pageable_count"), "pageable_count")
            for document in documents:
                if isinstance(document, dict):
                    place = _to_place(document)
                    places_by_id[place.place_id] = place
            if bool(meta.get("is_end")) or page >= MAX_PAGES:
                break
            page += 1

        places = tuple(sorted(places_by_id.values(), key=lambda item: (item.name, item.place_id)))
        return KakaoCategoryCollection(
            category_group_code=category,
            category_group_name=CATEGORY_GROUPS[category],
            center_longitude=(west + east) / 2,
            center_latitude=(south + north) / 2,
            radius_meters=0,
            api_total_count=total_count,
            pageable_count=pageable_count,
            collected_count=len(places),
            result_truncated=total_count > pageable_count or len(places) < min(total_count, pageable_count),
            places=places,
        )

    def collect_keyword_in_rectangle(
        self,
        *,
        query: str,
        west: float,
        south: float,
        east: float,
        north: float,
    ) -> KakaoKeywordCollection:
        """Collect one keyword from a WGS84 bounding rectangle."""
        normalized_query = query.strip()
        if not normalized_query:
            raise ValueError("Keyword query must not be empty.")
        _validate_rectangle(west, south, east, north)
        places_by_id: dict[str, KakaoPlace] = {}
        total_count = pageable_count = 0
        page = 1
        while True:
            payload = self._request_page(
                base_url=KEYWORD_SEARCH_BASE_URL,
                query=normalized_query,
                rect=f"{west},{south},{east},{north}",
                page=page,
            )
            meta = payload.get("meta")
            documents = payload.get("documents")
            if not isinstance(meta, dict) or not isinstance(documents, list):
                raise KakaoLocalApiError("Kakao Local API response has an invalid shape.")
            total_count = _non_negative_int(meta.get("total_count"), "total_count")
            pageable_count = _non_negative_int(meta.get("pageable_count"), "pageable_count")
            for document in documents:
                if isinstance(document, dict):
                    place = _to_place(document)
                    places_by_id[place.place_id] = place
            if bool(meta.get("is_end")) or page >= MAX_PAGES:
                break
            page += 1
        places = tuple(sorted(places_by_id.values(), key=lambda item: (item.name, item.place_id)))
        return KakaoKeywordCollection(
            query=normalized_query,
            api_total_count=total_count,
            pageable_count=pageable_count,
            collected_count=len(places),
            result_truncated=total_count > pageable_count or len(places) < min(total_count, pageable_count),
            places=places,
        )

    def inspect_category_in_rectangle(
        self, *, category_group_code: str, west: float, south: float, east: float, north: float
    ) -> KakaoCategoryMetadata:
        """Read only the first page metadata for a rectangle (one HTTP call)."""
        category = _validate_category(category_group_code)
        _validate_rectangle(west, south, east, north)
        payload = self._request_page(category_group_code=category, rect=f"{west},{south},{east},{north}", page=1)
        meta = payload.get("meta")
        if not isinstance(meta, dict):
            raise KakaoLocalApiError("Kakao Local API response has an invalid shape.")
        return KakaoCategoryMetadata(
            category_group_code=category,
            total_count=_non_negative_int(meta.get("total_count"), "total_count"),
            pageable_count=_non_negative_int(meta.get("pageable_count"), "pageable_count"),
        )

    def collect_categories_nearby(
        self,
        *,
        category_group_codes: Iterable[str],
        longitude: float,
        latitude: float,
        radius_meters: int = 2_000,
    ) -> tuple[KakaoCategoryCollection, ...]:
        codes = tuple(category_group_codes)
        if not codes:
            raise ValueError("At least one category_group_code is required.")
        return tuple(
            self.collect_category_nearby(
                category_group_code=code,
                longitude=longitude,
                latitude=latitude,
                radius_meters=radius_meters,
            )
            for code in codes
        )

    def _request_page(self, *, base_url: str | None = None, **parameters: Any) -> dict[str, Any]:
        query = urlencode({**parameters, "size": MAX_PAGE_SIZE})
        request = Request(
            f"{base_url or self._base_url}?{query}",
            headers={
                "Accept": "application/json",
                "Authorization": f"KakaoAK {self._rest_api_key}",
                "User-Agent": "TourismGapFinder/0.1",
            },
        )
        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise KakaoLocalApiError(f"Kakao Local API HTTP error ({exc.code}).") from exc
        except URLError as exc:
            raise KakaoLocalApiError(f"Kakao Local API connection failed: {exc.reason}") from exc
        except (TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise KakaoLocalApiError("Kakao Local API response could not be decoded.") from exc
        if not isinstance(payload, dict):
            raise KakaoLocalApiError("Kakao Local API top-level response must be an object.")
        return payload


def _validate_category(value: str) -> str:
    category = value.strip().upper()
    if category not in CATEGORY_GROUPS:
        raise ValueError("Unsupported category_group_code: " + value)
    return category


def _validate_coordinates(longitude: float, latitude: float) -> None:
    if not math.isfinite(longitude) or not math.isfinite(latitude):
        raise ValueError("Coordinates must be finite.")
    if not -180 <= longitude <= 180 or not -90 <= latitude <= 90:
        raise ValueError("Coordinates are out of range.")


def _validate_rectangle(west: float, south: float, east: float, north: float) -> None:
    _validate_coordinates(west, south)
    _validate_coordinates(east, north)
    if west >= east or south >= north:
        raise ValueError("Rectangle must satisfy west < east and south < north.")


def _non_negative_int(value: Any, field: str) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError) as exc:
        raise KakaoLocalApiError(f"Kakao Local API {field} is invalid.") from exc
    if parsed < 0:
        raise KakaoLocalApiError(f"Kakao Local API {field} must not be negative.")
    return parsed


def _to_place(document: dict[str, Any]) -> KakaoPlace:
    place_id = _text(document, "id")
    name = _text(document, "place_name")
    if not place_id or not name:
        raise KakaoLocalApiError("Kakao Local API place id or name is missing.")
    return KakaoPlace(
        place_id=place_id,
        name=name,
        category_group_code=_text(document, "category_group_code"),
        category_group_name=_text(document, "category_group_name"),
        category_name=_text(document, "category_name"),
        address=_text(document, "address_name"),
        road_address=_text(document, "road_address_name"),
        longitude=_float(document, "x"),
        latitude=_float(document, "y"),
        phone=_text(document, "phone"),
        place_url=_text(document, "place_url"),
        distance_meters=_optional_int(document.get("distance")),
    )


def _text(document: dict[str, Any], key: str) -> str:
    return str(document.get(key) or "").strip()


def _float(document: dict[str, Any], key: str) -> float:
    try:
        return float(_text(document, key))
    except ValueError as exc:
        raise KakaoLocalApiError(f"Kakao Local API place {key} is invalid.") from exc


def _optional_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(str(value))
    except ValueError as exc:
        raise KakaoLocalApiError("Kakao Local API place distance is invalid.") from exc
