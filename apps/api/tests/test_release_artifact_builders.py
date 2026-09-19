from __future__ import annotations

from dataclasses import dataclass
import csv
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

import pytest

from apps.api.app.schemas.analysis import HubReport, PerformanceScore, PortfolioReport
from hankkeut_calculation.gap_analyzer.models import (
    HubTouristSpot,
    HubTouristSpotReport,
    PortfolioMetric,
    PortfolioReport as ProducerPortfolioReport,
)
from scripts.build_release_artifacts import (
    _demand_scores_for_month,
    _write_json,
    build_datalab_pressure,
    build_relative_supply,
    collect_hubs,
    hubs_envelope,
    performance_envelope,
    portfolio_envelope,
    select_performance_peers,
    validate_kakao_database,
    validate_boundaries,
)


REGION = {
    "province_name": "경상북도",
    "region_name": "경주시",
    "administrative_type": "시",
}


def test_portfolio_and_hub_envelopes_match_api_contracts() -> None:
    portfolio = ProducerPortfolioReport(
        region_name="경주시",
        area_code="35",
        sigungu_code="2",
        area_square_km=1324.39,
        total_resource_count=10,
        total_count_per_square_km=0.0076,
        metrics=(PortfolioMetric(12, "관광지", 10, 100.0, 0.0076),),
    )
    hubs = HubTouristSpotReport(
        region_name="경주시",
        base_year_month="202608",
        area_code="47",
        sigungu_code="47130",
        limit=5,
        spots=(HubTouristSpot(1, "A1", "불국사"),),
    )

    portfolio_payload = portfolio_envelope("47130", REGION, portfolio)
    hub_payload = hubs_envelope("47130", REGION, hubs)

    assert portfolio_payload["target"]["region_id"] == "47130"
    assert hub_payload["target"]["region_id"] == "47130"
    PortfolioReport.model_validate(portfolio_payload["portfolio"])
    HubReport.model_validate(hub_payload["hubs"])


def test_hubs_use_legal_region_id_without_korservice_mapping() -> None:
    calls: list[dict[str, object]] = []

    class FakeHubClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def fetch_top_spots(self, **kwargs):
            calls.append(kwargs)
            return []

    with (
        mock.patch("scripts.build_release_artifacts.resolve_hub_service_key", return_value="key"),
        mock.patch("scripts.build_release_artifacts.HubTourApiClient", FakeHubClient),
    ):
        payload = collect_hubs(
            "28125", base_year_month="202608", limit=5, timeout=1
        )

    assert payload["target"]["region_id"] == "28125"
    assert calls == [{
        "base_year_month": "202608",
        "area_code": "28",
        "sigungu_code": "28125",
        "limit": 5,
    }]


@dataclass
class _Score:
    visitor_sum: float = 100.0
    resource_demand: float = 0.7
    demand_intensity: float = 0.8
    visitor_percentile: float = 0.6
    resource_demand_percentile: float = 0.7
    demand_intensity_percentile: float = 0.8
    composite_score: float = 0.69


def test_performance_envelope_matches_api_contract() -> None:
    payload = performance_envelope(
        "47130", REGION, _Score(), "202608", lambda _ym: "20260831"
    )
    assert payload["target"]["region_id"] == "47130"
    PerformanceScore.model_validate(payload["performance"])


def test_demand_month_resolves_current_and_legacy_code_alternatives() -> None:
    class FakeClient:
        def __init__(self, *args, **kwargs) -> None:
            pass

        def fetch_all_scores(self, *, base_ym: str, area_code: str):
            available = {
                "12": {"12150"},       # current reorganised code
                "41": {"41590"},       # pre-reorganisation direct city code
                "46": set(),
                "47": set(),
            }[area_code]
            return {
                metric: {
                    code: SimpleNamespace(value=1.0)
                    for code in available
                }
                for metric in (
                    "resource_service",
                    "resource_culture",
                    "intensity_stay",
                    "intensity_spend",
                )
            }

    configured = {
        "12150": ("46:46150",),
        "41590": ("41:41591", "41:41593", "41:41595", "41:41597"),
        "47130": ("47:47130",),
    }
    with mock.patch(
        "hankkeut_calculation.tourism_data.tourism_demand_api.TourismDemandApiClient",
        FakeClient,
    ):
        scores, usable = _demand_scores_for_month(
            "key", configured, base_year_month="202608", timeout=1, page_size=10
        )

    assert usable == {"12150": ("12:12150",), "41590": ("41:41590",)}
    assert "12:12150" in scores["resource_service"]


def test_peer_selection_uses_only_higher_scoring_structural_candidates(tmp_path: Path) -> None:
    peer_path = tmp_path / "peers.json"
    performance_dir = tmp_path / "performance"
    _write_json(peer_path, {"peers": [
        {"region_id": "47110"},
        {"region_id": "44210"},
        {"region_id": "48870"},
    ]})
    for region_id, score in {
        "47130": 0.5,
        "47110": 0.7,
        "44210": 0.6,
        "48870": 0.4,
    }.items():
        _write_json(
            performance_dir / f"{region_id}.json",
            {"performance": {"composite_score": score}},
        )

    selected = select_performance_peers(
        "47130",
        peer_artifact=peer_path,
        performance_dir=performance_dir,
        max_peers=3,
    )

    assert selected == ["47110", "44210"]


def test_peer_selection_refuses_missing_scores(tmp_path: Path) -> None:
    peer_path = tmp_path / "peers.json"
    _write_json(peer_path, {"peers": [{"region_id": "47110"}]})
    with pytest.raises(ValueError, match="composite performance score is unavailable"):
        select_performance_peers(
            "47130",
            peer_artifact=peer_path,
            performance_dir=tmp_path / "performance",
            max_peers=3,
        )


def test_boundary_validation_requires_complete_wgs84_region_set(tmp_path: Path) -> None:
    path = tmp_path / "boundaries.geojson"
    _write_json(path, {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "properties": {
                "region_id": "47130",
                "area_code": "47",
                "sigungu_code": "47130",
                "province_name": "경상북도",
                "region_name": "경주시",
            },
            "geometry": {
                "type": "Polygon",
                "coordinates": [[[129.0, 35.7], [129.1, 35.7], [129.0, 35.8], [129.0, 35.7]]],
            },
        }],
    })

    result = validate_boundaries(path, expected_region_ids={"47130"})

    assert result["region_count"] == 1


def test_database_run_drives_target_and_peer_pressure_and_relative_supply(
    tmp_path: Path,
) -> None:
    peer_dir = tmp_path / "peers"
    performance_dir = tmp_path / "performance"
    raw_root = tmp_path / "raw"
    peer_path = peer_dir / "47130.json"
    _write_json(peer_path, {"peers": [
        {"region_id": "47110"}, {"region_id": "44210"},
    ]})
    for region_id, score in {"47130": 0.5, "47110": 0.7, "44210": 0.6}.items():
        _write_json(
            performance_dir / f"{region_id}.json",
            {"performance": {"composite_score": score}},
        )
        _write_period_total_csv(raw_root / region_id / "navigation.csv")
    marker = tmp_path / "release" / "source-markers" / "kakao.json"

    run_data = _kakao_run(["47130", "47110", "44210"])
    with (
        mock.patch(
            "scripts.build_release_artifacts.required_advanced_region_ids",
            return_value=["47130", "47110", "44210"],
        ),
        mock.patch(
            "hankkeut_calculation.datalab_navigation.kakao_supply._read_latest_supply_region",
            side_effect=lambda _database_url, region_id: (
                run_data[0],
                [row for row in run_data[1] if row[0] == region_id],
            ),
        ),
    ):
        handoff = validate_kakao_database(
            "postgresql://example",
            peer_artifact_dir=peer_dir,
            performance_dir=performance_dir,
            marker=marker,
        )
        pressure = build_datalab_pressure(
            "47130",
            raw_root=raw_root,
            database_url="postgresql://example",
            peer_artifact=peer_path,
            performance_dir=performance_dir,
            period_start_ym="202509",
            period_end_ym="202608",
        )
        relative = build_relative_supply(
            "47130",
            peer_artifact=peer_path,
            performance_dir=performance_dir,
            database_url="postgresql://example",
            max_peers=3,
        )

    assert handoff["required_region_count"] == 3
    assert marker.is_file()
    assert pressure["target_region_id"] == "47130"
    assert pressure["peer_region_ids"] == ["47110", "44210"]
    assert pressure["peer_regions"] == ["포항시", "서산시"]
    assert [row["region_id"] for row in relative["peer_regions"]] == ["47110", "44210"]


def _write_period_total_csv(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rows = [
        ("자연관광", 10), ("역사관광", 10), ("문화관광", 20),
        ("체험관광", 10), ("레저스포츠", 10), ("쇼핑", 20),
        ("음식", 10), ("숙박", 10), ("기타관광", 10),
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["카테고리중분류명", "유형별 검색건수"])
        writer.writerows(rows)


def _kakao_run(region_ids: list[str]) -> tuple[dict, list[tuple]]:
    content_types = (
        "FOOD", "ACCOMMODATION", "CULTURE_TOURISM",
        "EXPERIENCE_TOURISM", "LEISURE_SPORTS", "SHOPPING",
    )
    metadata = {
        "run_id": "run-1",
        "taxonomy_version": "tourism-v1",
        "collected_at": "2026-09-19T00:00:00+09:00",
        "status": "completed",
    }
    rows = [
        (region_id, name, index + 1, True, 0)
        for region_id in region_ids
        for index, name in enumerate(content_types)
    ]
    return metadata, rows
