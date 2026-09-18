from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import mock

from fastapi.testclient import TestClient

from apps.api.app.deps import current_user
from apps.api.app.main import app
from apps.api.app.services import artifacts


def test_release_endpoints_require_authentication() -> None:
    override = app.dependency_overrides.pop(current_user)
    try:
        client = TestClient(app)
        protected = [
            "/regions/47130",
            "/regions/47130/structure",
            "/regions/47130/peers",
            "/regions/47130/portfolio",
            "/regions/47130/hubs",
            "/regions/47130/performance",
            "/regions/47130/gaps",
            "/regions/47130/report",
        ]
        assert all(client.get(path).status_code == 401 for path in protected)
        assert client.get(
            "/compare", params=[("region_ids", "47130"), ("region_ids", "47110")]
        ).status_code == 401
        assert client.get("/health").status_code == 200
        assert client.get("/regions").status_code == 200
        assert client.get("/provinces").status_code == 200
    finally:
        app.dependency_overrides[current_user] = override


def test_performance_and_compare_read_precomputed_artifacts() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        _write(root / "performance" / "47130.json", _performance("47130", "경주시", 0.8))
        _write(root / "performance" / "47110.json", _performance("47110", "포항시", 0.9))
        _write(root / "portfolios" / "47130.json", _portfolio("47130", "경주시", 100))
        _write(root / "portfolios" / "47110.json", _portfolio("47110", "포항시", 120))
        _write(root / "peer_candidates" / "47130.json", {
            "target": {"region_id": "47130", "region_name": "경주시"},
            "peers": [{"region_id": "47110", "region_name": "포항시", "similarity": 0.72}],
        })
        with mock.patch.object(artifacts, "ARTIFACT_ROOT", root):
            client = TestClient(app)
            performance = client.get("/regions/47130/performance")
            comparison = client.get(
                "/compare", params=[("region_ids", "47130"), ("region_ids", "47110")]
            )
    assert performance.status_code == 200
    assert performance.json()["composite_score"] == 0.8
    assert comparison.status_code == 200
    assert [item["region"]["region_id"] for item in comparison.json()["columns"]] == [
        "47130", "47110"
    ]
    assert comparison.json()["columns"][1]["similarity_to_first"] == 0.72


def test_portfolio_provider_unavailable_is_distinct_from_a_missing_artifact() -> None:
    with TemporaryDirectory() as directory, mock.patch.object(
        artifacts, "ARTIFACT_ROOT", Path(directory)
    ):
        response = TestClient(app).get("/regions/28125/portfolio")
    assert response.status_code == 409
    assert response.json()["detail"] == {
        "code": "PROVIDER_UNAVAILABLE",
        "region_id": "28125",
        "message": "해당 지역의 관광자원 상세 정보를 준비하고 있습니다.",
    }


def test_hubs_default_to_the_active_release_month() -> None:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        _write(root / "hubs" / "47130.json", {
            "target": {"region_id": "47130", "region_name": "경주시"},
            "hubs": {
                "region_name": "경주시",
                "base_year_month": "202608",
                "area_code": "35",
                "sigungu_code": "2",
                "limit": 5,
                "extracted_count": 0,
                "spots": [],
            },
        })
        with mock.patch.object(artifacts, "ARTIFACT_ROOT", root):
            response = TestClient(app).get("/regions/47130/hubs")
    assert response.status_code == 200
    assert response.json()["base_year_month"] == "202608"


def _performance(region_id: str, name: str, score: float) -> dict:
    return {
        "target": {"region_id": region_id, "region_name": name},
        "performance": {
            "region_name": name,
            "analysis_period": "20260101~20260131",
            "visitor_sum": 100.0,
            "resource_demand": 0.5,
            "demand_intensity": 0.5,
            "visitor_percentile": score,
            "resource_demand_percentile": score,
            "demand_intensity_percentile": score,
            "composite_score": score,
            "data_quality": {"unavailable_metrics": [], "note": "사전 계산 결과"},
        },
    }


def _portfolio(region_id: str, name: str, count: int) -> dict:
    return {
        "target": {"region_id": region_id, "region_name": name},
        "portfolio": {
            "region_name": name,
            "area_code": "35",
            "sigungu_code": "2",
            "area_square_km": 100.0,
            "total_resource_count": count,
            "total_count_per_square_km": count / 100,
            "metrics": [],
        },
    }


def _write(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
