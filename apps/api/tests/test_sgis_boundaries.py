from __future__ import annotations

from unittest import mock

import pytest
from pyproj import Transformer

from scripts.build_sgis_boundaries import normalize_boundaries


def _sgis_polygon(province: str, municipality: str) -> dict:
    to_5179 = Transformer.from_crs("EPSG:4326", "EPSG:5179", always_xy=True)
    points = [
        to_5179.transform(127.0, 37.0),
        to_5179.transform(127.1, 37.0),
        to_5179.transform(127.1, 37.1),
        to_5179.transform(127.0, 37.0),
    ]
    return {
        "type": "Feature",
        "properties": {"adm_nm": f"{province} {municipality}"},
        "geometry": {"type": "Polygon", "coordinates": [[list(point) for point in points]]},
    }


def test_normalizes_sgis_5179_geometry_to_wgs84() -> None:
    rows = [{
        "region_id": "11110",
        "province_name": "서울특별시",
        "region_name": "종로구",
        "administrative_type": "자치구",
    }]
    with mock.patch(
        "scripts.build_sgis_boundaries.regions.tour_api_code", return_value=("1", "1")
    ):
        payload = normalize_boundaries(
            [_sgis_polygon("서울특별시", "종로구")],
            region_rows=rows,
            mapping_rows=[],
        )

    feature = payload["features"][0]
    longitude, latitude = feature["geometry"]["coordinates"][0][0][0]
    assert longitude == pytest.approx(127.0, abs=1e-6)
    assert latitude == pytest.approx(37.0, abs=1e-6)
    assert feature["properties"]["region_id"] == "11110"


def test_split_region_requires_an_official_override() -> None:
    rows = [{
        "region_id": "28125",
        "province_name": "인천광역시",
        "region_name": "제물포구",
        "administrative_type": "자치구",
    }]
    mapping_rows = [
        {
            "region_id": "28125",
            "sgis_province": "인천광역시",
            "sgis_municipality": "동구",
            "weight": "1.0",
        },
        {
            "region_id": "28125",
            "sgis_province": "인천광역시",
            "sgis_municipality": "중구",
            "weight": "0.5",
        },
    ]

    with pytest.raises(ValueError, match="missing_region_ids=\['28125'\]"):
        normalize_boundaries(
            [_sgis_polygon("인천광역시", "동구")],
            region_rows=rows,
            mapping_rows=mapping_rows,
        )


def test_override_can_supply_boundary_and_missing_tour_api_code() -> None:
    rows = [{
        "region_id": "28125",
        "province_name": "인천광역시",
        "region_name": "제물포구",
        "administrative_type": "자치구",
    }]
    override = {
        "type": "Feature",
        "properties": {
            "region_id": "28125",
            "area_code": "99",
            "sigungu_code": "1",
        },
        "geometry": {
            "type": "Polygon",
            "coordinates": [[[126.6, 37.4], [126.7, 37.4], [126.6, 37.4]]],
        },
    }
    with mock.patch(
        "scripts.build_sgis_boundaries.regions.tour_api_code", return_value=None
    ):
        payload = normalize_boundaries(
            [],
            region_rows=rows,
            mapping_rows=[],
            override_features=[override],
        )

    properties = payload["features"][0]["properties"]
    assert properties["area_code"] == "99"
    assert properties["sigungu_code"] == "1"
