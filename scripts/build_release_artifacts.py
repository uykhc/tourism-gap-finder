"""Build API-ready release artifacts from the existing analysis producers.

The analysis CLIs predate the API release contract and write human-readable
file names or nationwide aggregate files.  This adapter keeps the public API
contract in one place: every artifact is named by the five-digit ``region_id``
and carries an explicit target envelope.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

from apps.api.app.services import regions
from hankkeut_calculation.gap_analyzer.analysis import analyze_portfolio
from hankkeut_calculation.gap_analyzer.hub_api import HubTourApiClient
from hankkeut_calculation.gap_analyzer.models import HubTouristSpotReport, PortfolioReport
from hankkeut_calculation.gap_analyzer.tour_api import TourApiClient
from hankkeut_calculation.tourism_data.config import (
    resolve_hub_service_key,
    resolve_portfolio_service_key,
    resolve_service_key,
    resolve_visitor_service_key,
)

ADVANCED_REPORT_TARGETS = ("26350", "41590", "51150", "47130", "12130")
PERFORMANCE_PEER_CANDIDATE_LIMIT = 10


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    portfolio = subparsers.add_parser("portfolio", help="Build one API portfolio artifact.")
    portfolio.add_argument("--region-id", required=True)
    portfolio.add_argument("--output", required=True, type=Path)
    portfolio.add_argument("--timeout", type=float, default=30.0)
    portfolio.add_argument("--page-size", type=int, default=1000)

    hubs = subparsers.add_parser("hubs", help="Build one API hub artifact.")
    hubs.add_argument("--region-id", required=True)
    hubs.add_argument("--base-year-month", required=True)
    hubs.add_argument("--output", required=True, type=Path)
    hubs.add_argument("--limit", type=int, default=5)
    hubs.add_argument("--timeout", type=float, default=30.0)

    performance = subparsers.add_parser(
        "performance", help="Build nationwide per-region performance artifacts."
    )
    performance.add_argument("--output-dir", required=True, type=Path)
    performance.add_argument("--base-year-month", required=True)
    performance.add_argument("--timeout", type=float, default=45.0)
    performance.add_argument("--page-size", type=int, default=1000)

    kakao = subparsers.add_parser(
        "kakao-content", help="Migrate and populate the nationwide Kakao content store."
    )
    kakao.add_argument("--boundaries", required=True, type=Path)
    kakao.add_argument("--marker", required=True, type=Path)
    kakao.add_argument(
        "--migration",
        type=Path,
        default=Path("db/migrations/001_content_collection.sql"),
    )

    store_artifact = subparsers.add_parser(
        "store-artifact", help="Upload one report input JSON artifact to Supabase."
    )
    store_artifact.add_argument("--region-id", required=True)
    store_artifact.add_argument(
        "--artifact-type",
        required=True,
        choices=("peer_candidates", "relative_supply", "datalab_navigation"),
    )
    store_artifact.add_argument("--input", required=True, type=Path)
    store_artifact.add_argument("--content-database-url")

    selected_peers = subparsers.add_parser(
        "select-peers", help="Show the top-10 similarity candidates and selected high-performance peers."
    )
    selected_peers.add_argument("--region-id", required=True)
    selected_peers.add_argument("--peer-artifact", required=True, type=Path)
    selected_peers.add_argument("--performance-dir", required=True, type=Path)
    selected_peers.add_argument("--max-peers", type=int, default=3)

    handoff = subparsers.add_parser(
        "kakao-db", help="Validate one completed Kakao database collection run."
    )
    handoff.add_argument("--content-database-url")
    handoff.add_argument("--peer-artifact-dir", required=True, type=Path)
    handoff.add_argument("--performance-dir", required=True, type=Path)
    handoff.add_argument("--marker", required=True, type=Path)
    handoff.add_argument("--max-peers", type=int, default=3)

    pressure = subparsers.add_parser(
        "datalab-pressure", help="Build target and performance-backed Peer search pressure."
    )
    pressure.add_argument("--region-id", required=True)
    pressure.add_argument("--raw-root", required=True, type=Path)
    pressure.add_argument("--content-database-url")
    pressure.add_argument("--peer-artifact", required=True, type=Path)
    pressure.add_argument("--performance-dir", required=True, type=Path)
    pressure.add_argument("--period-start-ym", required=True)
    pressure.add_argument("--period-end-ym", required=True)
    pressure.add_argument("--output", required=True, type=Path)
    pressure.add_argument("--max-peers", type=int, default=3)

    relative = subparsers.add_parser(
        "relative-supply", help="Build one fixed-run database-backed relative-supply artifact."
    )
    relative.add_argument("--region-id", required=True)
    relative.add_argument("--peer-artifact", required=True, type=Path)
    relative.add_argument("--performance-dir", required=True, type=Path)
    relative.add_argument("--content-database-url")
    relative.add_argument("--output", required=True, type=Path)
    relative.add_argument("--max-peers", type=int, default=3)

    ai_report = subparsers.add_parser("ai-report", help="Build one source-grounded AI report.")
    ai_report.add_argument("--region-id", required=True)
    ai_report.add_argument("--supply-pressure-report", required=True, type=Path)
    ai_report.add_argument("--relative-supply-report", required=True, type=Path)
    ai_report.add_argument("--peer-artifact", required=True, type=Path)
    ai_report.add_argument("--performance-dir", required=True, type=Path)
    ai_report.add_argument("--output", required=True, type=Path)
    ai_report.add_argument("--max-peers", type=int, default=3)
    ai_report.add_argument("--max-output-tokens", type=int, default=8_000)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command == "portfolio":
            _write_json(args.output, collect_portfolio(
                args.region_id, timeout=args.timeout, page_size=args.page_size
            ))
            return 0
        if args.command == "hubs":
            _write_json(args.output, collect_hubs(
                args.region_id,
                base_year_month=args.base_year_month,
                limit=args.limit,
                timeout=args.timeout,
            ))
            return 0
        if args.command == "relative-supply":
            payload = build_relative_supply(
                args.region_id,
                peer_artifact=args.peer_artifact,
                performance_dir=args.performance_dir,
                database_url=args.content_database_url or resolve_content_database_url(),
                max_peers=args.max_peers,
            )
            _write_json(args.output, payload)
            store_analysis_artifact(
                args.region_id, "relative_supply", payload,
                args.content_database_url or resolve_content_database_url(),
            )
            return 0
        if args.command == "datalab-pressure":
            payload = build_datalab_pressure(
                args.region_id,
                raw_root=args.raw_root,
                database_url=args.content_database_url or resolve_content_database_url(),
                peer_artifact=args.peer_artifact,
                performance_dir=args.performance_dir,
                period_start_ym=args.period_start_ym,
                period_end_ym=args.period_end_ym,
                max_peers=args.max_peers,
            )
            _write_json(args.output, payload)
            store_analysis_artifact(
                args.region_id, "datalab_navigation", payload,
                args.content_database_url or resolve_content_database_url(),
            )
            return 0
        if args.command == "store-artifact":
            store_analysis_artifact(
                args.region_id,
                args.artifact_type,
                _read_json(args.input),
                args.content_database_url or resolve_content_database_url(),
            )
            print(f"stored {args.artifact_type}: {args.region_id}")
            return 0
        if args.command == "select-peers":
            print(json.dumps(
                performance_peer_selection(
                    args.region_id,
                    peer_artifact=args.peer_artifact,
                    performance_dir=args.performance_dir,
                    max_peers=args.max_peers,
                ),
                ensure_ascii=False,
                indent=2,
            ))
            return 0
        if args.command == "kakao-db":
            validate_kakao_database(
                args.content_database_url or resolve_content_database_url(),
                peer_artifact_dir=args.peer_artifact_dir,
                performance_dir=args.performance_dir,
                marker=args.marker,
                max_peers=args.max_peers,
            )
            return 0
        if args.command == "ai-report":
            return build_ai_report(
                args.region_id,
                supply_pressure_report=args.supply_pressure_report,
                relative_supply_report=args.relative_supply_report,
                peer_artifact=args.peer_artifact,
                performance_dir=args.performance_dir,
                output=args.output,
                max_peers=args.max_peers,
                max_output_tokens=args.max_output_tokens,
            )
        if args.command == "kakao-content":
            return collect_kakao_content(args.boundaries, args.migration, args.marker)
        count = collect_performance(
            args.output_dir,
            base_year_month=args.base_year_month,
            timeout=args.timeout,
            page_size=args.page_size,
        )
        print(f"performance artifacts: {count} -> {args.output_dir}")
        return 0 if count == len(regions.all_region_ids()) else 1
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"Error: {exc}")
        return 2


def resolve_content_database_url() -> str:
    return resolve_service_key(
        env_names=("CONTENT_DATABASE_URL", "AUTH_DATABASE_URL"),
    ) or ""


def store_analysis_artifact(
    region_id: str, artifact_type: str, payload: dict[str, Any], database_url: str
) -> None:
    from hankkeut_calculation.ai_reports.analysis_artifact_store import (
        RegionAnalysisArtifactStore,
    )

    RegionAnalysisArtifactStore(database_url).save(
        region_id=region_id,
        artifact_type=artifact_type,
        payload=payload,
    )


def collect_portfolio(region_id: str, *, timeout: float, page_size: int) -> dict[str, Any]:
    region, area_code, sigungu_code = _tour_region(region_id)
    feature = regions.find_region_features(region_id)
    area_km2 = None if feature is None else feature.get("area_km2")
    if area_km2 is None or area_km2 <= 0:
        raise ValueError(f"area_km2 is unavailable: {region_id}")
    service_key = resolve_portfolio_service_key()
    if not service_key:
        raise ValueError("TOUR_API_SERVICE_KEY or KOR_TOUR_API_SERVICE_KEY is required")
    resources = TourApiClient(
        service_key, timeout_seconds=timeout, page_size=page_size
    ).fetch_region_resources(area_code=area_code, sigungu_code=sigungu_code)
    report = analyze_portfolio(
        resources,
        region_name=region["region_name"],
        area_code=area_code,
        sigungu_code=sigungu_code,
        area_square_km=area_km2,
    )
    return portfolio_envelope(region_id, region, report)


def collect_hubs(
    region_id: str, *, base_year_month: str, limit: int, timeout: float
) -> dict[str, Any]:
    if len(base_year_month) != 6 or not base_year_month.isdigit():
        raise ValueError("base_year_month must use YYYYMM")
    region = regions.find_region(region_id)
    if region is None:
        raise ValueError(f"unknown region_id: {region_id}")
    # The hub API uses the legal-dong five-digit region code and its province prefix,
    # not KorService's separate area/sigungu code pair.
    area_code = region_id[:2]
    service_key = resolve_hub_service_key()
    if not service_key:
        raise ValueError("TOUR_API_SERVICE_KEY or HUB_TOUR_API_SERVICE_KEY is required")
    spots = HubTourApiClient(service_key, timeout_seconds=timeout).fetch_top_spots(
        base_year_month=base_year_month,
        area_code=area_code,
        sigungu_code=region_id,
        limit=limit,
    )
    report = HubTouristSpotReport(
        region_name=region["region_name"],
        base_year_month=base_year_month,
        area_code=area_code,
        sigungu_code=region_id,
        limit=limit,
        spots=tuple(spots),
    )
    return hubs_envelope(region_id, region, report)


def collect_performance(
    output_dir: Path, *, base_year_month: str, timeout: float, page_size: int
) -> int:
    from apps.api.app.services.performance import (
        DEMAND_INTENSITY_WEIGHT,
        RESOURCE_DEMAND_WEIGHT,
        VISITOR_WEIGHT,
        VisitorScorer,
        _regions_with_codes,
        _visitor_total,
    )
    from hankkeut_evaluation import visitor_portfolio_benchmark as benchmark

    region_ids = list(regions.all_region_ids())
    scorer = VisitorScorer(timeout_seconds=timeout, page_size=page_size)
    coded = _regions_with_codes(region_ids)
    if len(coded) != len(region_ids):
        missing = sorted(set(region_ids) - set(coded))
        raise ValueError("performance demand codes are missing: " + ", ".join(missing))
    service_key = resolve_visitor_service_key()
    if not service_key:
        raise ValueError("VISITOR_API_SERVICE_KEY or TOUR_API_SERVICE_KEY is required")
    if len(base_year_month) != 6 or not base_year_month.isdigit():
        raise ValueError("base_year_month must use YYYYMM")
    demand_scores, usable_codes = _demand_scores_for_month(
        service_key,
        coded,
        base_year_month=base_year_month,
        timeout=timeout,
        page_size=page_size,
    )
    if len(usable_codes) < 2:
        raise ValueError(
            f"fewer than two regions have all four demand metrics for {base_year_month}"
        )
    visitor_sums = scorer._visitor_sums(service_key, base_year_month)
    rows: list[dict[str, Any]] = []
    scored_codes: dict[str, tuple[str, ...]] = {}
    for region_id, codes in usable_codes.items():
        total = _visitor_total(region_id, codes, visitor_sums)
        if total is not None:
            scored_codes[region_id] = codes
            rows.append({
                "region_id": region_id,
                "region_name": regions.find_region(region_id)["region_name"],
                "daily_visitor_sum": total,
            })
    scores = benchmark.build_regional_tourism_scores(
        rows,
        demand_scores,
        region_sigungu_codes=scored_codes,
        visitor_weight=VISITOR_WEIGHT,
        resource_demand_weight=RESOURCE_DEMAND_WEIGHT,
        demand_intensity_weight=DEMAND_INTENSITY_WEIGHT,
        region_labels={rid: regions.find_region(rid)["region_name"] for rid in scored_codes},
        province_names={rid: regions.find_region(rid)["province_name"] for rid in scored_codes},
    )
    by_id = {item.region_id: item for item in scores if item.region_id}
    for region_id in region_ids:
        score = by_id.get(region_id)
        if score is None:
            continue
        region = regions.find_region(region_id)
        _write_json(
            output_dir / f"{region_id}.json",
            performance_envelope(
                region_id, region, score, base_year_month, benchmark._last_day_of_month
            ),
        )
    return len(by_id)


def _demand_scores_for_month(
    service_key: str,
    configured_codes: dict[str, tuple[str, ...]],
    *,
    base_year_month: str,
    timeout: float,
    page_size: int,
) -> tuple[dict[str, dict[str, Any]], dict[str, tuple[str, ...]]]:
    """Read one release month and resolve administrative-code transitions.

    The demand API changes code systems on the effective month of a municipal
    reorganisation.  The committed table retains the provider code needed for
    older months; the current five-digit region id is therefore also tried as
    an alternative.  Alternatives are never averaged together and a region is
    kept only when every code in one alternative has all four metrics.
    """
    from hankkeut_calculation.tourism_data.tourism_demand_api import (
        TourismDemandApiClient,
    )

    metric_names = (
        "resource_service",
        "resource_culture",
        "intensity_stay",
        "intensity_spend",
    )
    alternatives: dict[str, tuple[tuple[str, ...], ...]] = {}
    for region_id, legacy_or_district_codes in configured_codes.items():
        direct = (f"{region_id[:2]}:{region_id}",)
        candidates = [direct]
        if legacy_or_district_codes != direct:
            candidates.append(legacy_or_district_codes)
        alternatives[region_id] = tuple(candidates)

    areas = sorted({
        key.split(":", 1)[0]
        for candidates in alternatives.values()
        for candidate in candidates
        for key in candidate
    })
    client = TourismDemandApiClient(
        service_key, timeout_seconds=timeout, page_size=page_size
    )
    merged: dict[str, dict[str, Any]] = {name: {} for name in metric_names}
    for area in areas:
        scores = client.fetch_all_scores(base_ym=base_year_month, area_code=area)
        for metric in metric_names:
            merged[metric].update({
                f"{area}:{sigungu}": record
                for sigungu, record in scores[metric].items()
            })

    usable: dict[str, tuple[str, ...]] = {}
    for region_id, candidates in alternatives.items():
        for candidate in candidates:
            if all(all(key in merged[metric] for key in candidate) for metric in metric_names):
                usable[region_id] = candidate
                break
    return merged, usable


def collect_kakao_content(boundaries: Path, migration: Path, marker: Path) -> int:
    from hankkeut_calculation.kakao_places.tourism_cli import main as kakao_main

    database_url = os.getenv("CONTENT_DATABASE_URL") or os.getenv("AUTH_DATABASE_URL")
    if not database_url:
        raise ValueError("CONTENT_DATABASE_URL or AUTH_DATABASE_URL is required")
    try:
        import psycopg
    except ImportError as exc:
        raise ValueError("psycopg is required for the content database") from exc
    validate_boundaries(boundaries)
    sql = migration.read_text(encoding="utf-8")
    connection_url = database_url.replace("postgresql+psycopg://", "postgresql://", 1)
    with psycopg.connect(connection_url) as connection:
        connection.execute(sql)
    status = kakao_main(["--boundaries", str(boundaries)])
    if status != 0:
        return status
    _write_json(marker, {
        "status": "complete",
        "boundary_file": str(boundaries),
        "region_count": len(regions.all_region_ids()),
    })
    return 0


def validate_boundaries(
    path: Path, *, expected_region_ids: set[str] | None = None
) -> dict[str, Any]:
    payload = _read_json(path)
    if payload.get("type") != "FeatureCollection" or not isinstance(payload.get("features"), list):
        raise ValueError("national boundaries must be a GeoJSON FeatureCollection")
    expected = expected_region_ids if expected_region_ids is not None else set(regions.all_region_ids())
    found: set[str] = set()
    for feature in payload["features"]:
        if not isinstance(feature, dict):
            raise ValueError("boundary feature must be an object")
        properties = feature.get("properties")
        geometry = feature.get("geometry")
        if not isinstance(properties, dict) or not isinstance(geometry, dict):
            raise ValueError("boundary feature requires properties and geometry")
        region_id = str(properties.get("region_id") or "").strip()
        required = ("area_code", "sigungu_code", "province_name", "region_name")
        if not region_id or any(not str(properties.get(name) or "").strip() for name in required):
            raise ValueError("boundary properties are incomplete")
        if region_id in found:
            raise ValueError(f"duplicate boundary region_id: {region_id}")
        if not _wgs84_coordinates(geometry.get("coordinates")):
            raise ValueError(f"boundary is not valid WGS84 longitude/latitude: {region_id}")
        found.add(region_id)
    missing = sorted(expected - found)
    extra = sorted(found - expected)
    if missing or extra:
        raise ValueError(f"boundary region mismatch: missing={missing}, extra={extra}")
    return {"region_count": len(found), "region_ids": sorted(found)}


def _wgs84_coordinates(value: Any) -> bool:
    if not isinstance(value, list) or not value:
        return False
    if len(value) >= 2 and all(isinstance(item, (int, float)) for item in value[:2]):
        longitude, latitude = float(value[0]), float(value[1])
        return 124.0 <= longitude <= 132.0 and 32.0 <= latitude <= 39.5
    return all(_wgs84_coordinates(item) for item in value)


def build_relative_supply(
    region_id: str,
    *,
    peer_artifact: Path,
    performance_dir: Path,
    database_url: str,
    max_peers: int,
) -> dict[str, Any]:
    from hankkeut_calculation.datalab_navigation.relative_supply import (
        CONTENT_TYPES,
        build_relative_supply_report,
    )
    from hankkeut_calculation.datalab_navigation.kakao_supply import (
        PostgresKakaoSupplyProvider,
    )

    peer_ids = select_performance_peers(
        region_id,
        peer_artifact=peer_artifact,
        performance_dir=performance_dir,
        max_peers=max_peers,
    )
    if not peer_ids:
        raise ValueError(f"no performance-backed peer is available: {region_id}")
    provider = PostgresKakaoSupplyProvider(
        database_url,
        required_region_ids=(region_id, *peer_ids),
        require_complete=True,
    )

    def collection(selected_id: str) -> dict[str, Any]:
        region = regions.find_region(selected_id)
        if region is None:
            raise ValueError(f"unknown region_id: {selected_id}")
        supply = provider.get_region(selected_id, tuple(CONTENT_TYPES))
        return {
            "region_id": selected_id,
            "region_name": region["region_name"],
            "content_type_counts": supply["content_type_counts"],
            "is_complete": supply["is_complete"],
        }

    target = collection(region_id)
    peers = [collection(peer_id) for peer_id in peer_ids]
    selected_ids = [region_id, *peer_ids]
    area_by_name = {
        regions.find_region(item_id)["region_name"]: regions.find_region_features(item_id)["area_km2"]
        for item_id in selected_ids
    }
    result = build_relative_supply_report(
        target_region=target,
        peer_regions=peers,
        area_km2_by_region=area_by_name,
    )
    result["target_region"]["region_id"] = region_id
    for row, peer_id in zip(result["peer_regions"], peer_ids, strict=True):
        row["region_id"] = peer_id
    return result


def required_advanced_region_ids(
    *,
    peer_artifact_dir: Path,
    performance_dir: Path,
    max_peers: int = 3,
) -> list[str]:
    selected: list[str] = []
    for target_id in ADVANCED_REPORT_TARGETS:
        selected.append(target_id)
        selected.extend(select_performance_peers(
            target_id,
            peer_artifact=peer_artifact_dir / f"{target_id}.json",
            performance_dir=performance_dir,
            max_peers=max_peers,
        ))
    return list(dict.fromkeys(selected))


def validate_kakao_database(
    database_url: str,
    *,
    peer_artifact_dir: Path,
    performance_dir: Path,
    marker: Path,
    max_peers: int = 3,
) -> dict[str, Any]:
    from hankkeut_calculation.datalab_navigation.kakao_supply import (
        PostgresKakaoSupplyProvider,
    )

    required_ids = required_advanced_region_ids(
        peer_artifact_dir=peer_artifact_dir,
        performance_dir=performance_dir,
        max_peers=max_peers,
    )
    provider = PostgresKakaoSupplyProvider(
        database_url,
        required_region_ids=required_ids,
        require_complete=True,
    )
    result = {
        "status": "complete",
        "run_id": provider.run.run_id,
        "taxonomy_version": provider.run.taxonomy_version,
        "collected_at": provider.run.collected_at,
        "required_region_ids": required_ids,
        "required_region_count": len(required_ids),
        "normalized_sha256": provider.run.normalized_sha256,
    }
    _write_json(marker, result)
    return result


def build_datalab_pressure(
    region_id: str,
    *,
    raw_root: Path,
    database_url: str,
    peer_artifact: Path,
    performance_dir: Path,
    period_start_ym: str,
    period_end_ym: str,
    max_peers: int = 3,
) -> dict[str, Any]:
    from hankkeut_calculation.datalab_navigation.kakao_supply import (
        PostgresKakaoSupplyProvider,
    )
    from hankkeut_calculation.datalab_navigation.navigation_demand import (
        build_supply_pressure_report,
        import_navigation_demand_csv,
        load_navigation_demand_taxonomy,
    )
    from hankkeut_calculation.datalab_navigation.peer_comparison import (
        build_peer_supply_pressure_comparison,
    )

    peer_ids = select_performance_peers(
        region_id,
        peer_artifact=peer_artifact,
        performance_dir=performance_dir,
        max_peers=max_peers,
    )
    if not peer_ids:
        raise ValueError(f"no performance-backed peer is available: {region_id}")
    selected_ids = [region_id, *peer_ids]
    provider = PostgresKakaoSupplyProvider(
        database_url,
        required_region_ids=selected_ids,
        require_complete=True,
    )
    taxonomy = load_navigation_demand_taxonomy()

    def pressure(selected_id: str) -> dict[str, Any]:
        region = regions.find_region(selected_id)
        if region is None:
            raise ValueError(f"unknown region_id: {selected_id}")
        demand = import_navigation_demand_csv(
            raw_root / selected_id / "navigation.csv",
            region_name=region["region_name"],
            taxonomy=taxonomy,
            period_start_ym=period_start_ym,
            period_end_ym=period_end_ym,
        )
        return build_supply_pressure_report(
            demand,
            taxonomy=taxonomy,
            region_id=selected_id,
            supply_provider=provider,
            month_count=12,
        )

    target_report = pressure(region_id)
    peer_reports = [pressure(peer_id) for peer_id in peer_ids]
    peer_names = [regions.find_region(peer_id)["region_name"] for peer_id in peer_ids]
    result = build_peer_supply_pressure_comparison(
        target_report,
        peer_reports=peer_reports,
        peer_regions=peer_names,
        max_peers=max_peers,
    )
    result["target_region_id"] = region_id
    result["peer_region_ids"] = peer_ids
    return result


def build_ai_report(
    region_id: str,
    *,
    supply_pressure_report: Path,
    relative_supply_report: Path,
    peer_artifact: Path,
    performance_dir: Path,
    output: Path,
    max_peers: int,
    max_output_tokens: int,
) -> int:
    from hankkeut_calculation.ai_reports.cli import main as ai_main

    peer_ids = select_performance_peers(
        region_id,
        peer_artifact=peer_artifact,
        performance_dir=performance_dir,
        max_peers=max_peers,
    )
    peer_names = [
        f"{region['province_name']} {region['region_name']}"
        for peer_id in peer_ids
        if (region := regions.find_region(peer_id)) is not None
    ]
    if not peer_names:
        raise ValueError(f"no performance-backed peer is available: {region_id}")
    priority_types = select_ai_priority_content_types(
        supply_pressure_report=supply_pressure_report,
        relative_supply_report=relative_supply_report,
    )
    argv = [
        "--region-id", region_id,
        "--supply-pressure-report", str(supply_pressure_report),
        "--relative-supply-report", str(relative_supply_report),
        "--output", str(output),
        "--search-cases",
        "--max-output-tokens", str(max_output_tokens),
    ]
    for name in peer_names:
        argv.extend(("--peer-region", name))
    for content_type in priority_types:
        argv.extend(("--selected-content-type", content_type))
    return ai_main(argv)


def select_ai_priority_content_types(
    *, supply_pressure_report: Path, relative_supply_report: Path
) -> list[str]:
    """Fix the LLM input to the release builder's deterministic screen result."""
    pressure = _read_json(supply_pressure_report)
    relative = _read_json(relative_supply_report)
    relative_rows = {
        str(item.get("content_type")): item
        for item in relative.get("content_type_comparisons", [])
        if isinstance(item, dict) and item.get("content_type")
    }
    context = pressure.get("ai_report_context")
    if not isinstance(context, dict):
        raise ValueError("supply-pressure report is missing ai_report_context")
    pressure_rows = {
        str(item.get("content_type")): item
        for item in context.get("peer_supply_pressure_comparison", [])
        if isinstance(item, dict) and item.get("content_type")
    }
    pressure_order = [
        str(item) for item in context.get("priority_order_by_individual_peer_pressure", [])
        if str(item) in pressure_rows
    ]
    all_types = list(dict.fromkeys([*pressure_order, *relative_rows, *pressure_rows]))
    ranked: list[tuple[int, int, str]] = []
    for content_type in all_types:
        relative_candidate = int(relative_rows.get(content_type, {}).get("candidate_peer_count", 0)) > 0
        pressure_candidate = int(pressure_rows.get(content_type, {}).get("candidate_peer_count", 0)) > 0
        signal_rank = 0 if relative_candidate and pressure_candidate else 1 if (relative_candidate or pressure_candidate) else 2
        pressure_rank = pressure_order.index(content_type) if content_type in pressure_order else len(pressure_order)
        ranked.append((signal_rank, pressure_rank, content_type))
    return [content_type for _, _, content_type in sorted(ranked)[:3]]


def select_performance_peers(
    region_id: str,
    *,
    peer_artifact: Path,
    performance_dir: Path,
    max_peers: int,
) -> list[str]:
    selection = performance_peer_selection(
        region_id,
        peer_artifact=peer_artifact,
        performance_dir=performance_dir,
        max_peers=max_peers,
    )
    return [str(item["region_id"]) for item in selection["selected_peers"]]


def performance_peer_selection(
    region_id: str,
    *,
    peer_artifact: Path,
    performance_dir: Path,
    max_peers: int,
) -> dict[str, Any]:
    """Fixed policy: top 10 structural candidates, then performance-score top 3."""
    if max_peers < 1:
        raise ValueError("max_peers must be positive")
    peer_payload = _read_json(peer_artifact)
    candidates = sorted(
        (item for item in peer_payload.get("peers", []) if isinstance(item, dict) and item.get("region_id")),
        key=lambda item: (int(item.get("rank", 10**9)), str(item.get("region_id"))),
    )[:PERFORMANCE_PEER_CANDIDATE_LIMIT]
    target_score = _performance_value(performance_dir / f"{region_id}.json")
    evaluated: list[dict[str, Any]] = []
    for candidate in candidates:
        peer_id = str(candidate["region_id"])
        score = _performance_value(performance_dir / f"{peer_id}.json")
        evaluated.append({
            "region_id": peer_id,
            "region_name": candidate.get("region_name"),
            "similarity_rank": int(candidate.get("rank", 0)),
            "similarity": candidate.get("similarity"),
            "composite_score": score,
            "is_higher_performance": score > target_score,
        })
    selected = sorted(
        evaluated,
        key=lambda item: (-float(item["composite_score"]), int(item["similarity_rank"]), str(item["region_id"])),
    )[:max_peers]
    return {
        "policy": "top_10_structural_similarity_then_performance_score_top_3",
        "target_region_id": region_id,
        "target_composite_score": target_score,
        "similarity_candidates": evaluated,
        "selected_peers": selected,
    }


def _performance_value(path: Path) -> float:
    try:
        payload = _read_json(path)
    except ValueError as exc:
        raise ValueError(f"composite performance score is unavailable: {path}") from exc
    performance = payload.get("performance")
    value = performance.get("composite_score") if isinstance(performance, dict) else None
    if not isinstance(value, (int, float)):
        raise ValueError(f"composite performance score is unavailable: {path}")
    return float(value)


def _read_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be an object: {path}")
    return payload


def portfolio_envelope(
    region_id: str, region: dict[str, Any], report: PortfolioReport
) -> dict[str, Any]:
    return {"target": _target(region_id, region), "portfolio": report.to_dict()}


def hubs_envelope(
    region_id: str, region: dict[str, Any], report: HubTouristSpotReport
) -> dict[str, Any]:
    return {"target": _target(region_id, region), "hubs": report.to_dict()}


def performance_envelope(
    region_id: str,
    region: dict[str, Any],
    score: Any,
    base_ym: str,
    last_day: Any,
) -> dict[str, Any]:
    period = f"{base_ym}01~{last_day(base_ym)}"
    return {
        "target": _target(region_id, region),
        "performance": {
            "region_name": region["region_name"],
            "analysis_period": period,
            "visitor_sum": score.visitor_sum,
            "resource_demand": score.resource_demand,
            "demand_intensity": score.demand_intensity,
            "visitor_percentile": score.visitor_percentile,
            "resource_demand_percentile": score.resource_demand_percentile,
            "demand_intensity_percentile": score.demand_intensity_percentile,
            "composite_score": score.composite_score,
            "data_quality": {
                "unavailable_metrics": [],
                "note": "방문자 수와 관광 수요지수의 최근 공통 공표월 사전 계산 결과",
            },
        },
    }


def _tour_region(region_id: str) -> tuple[dict[str, Any], str, str]:
    region = regions.find_region(region_id)
    if region is None:
        raise ValueError(f"unknown region_id: {region_id}")
    codes = regions.tour_api_code(region_id)
    if codes is None:
        raise ValueError(f"TourAPI code is unavailable: {region_id}")
    return region, codes[0], codes[1]


def _target(region_id: str, region: dict[str, Any]) -> dict[str, str]:
    return {
        "region_id": region_id,
        "province_name": str(region["province_name"]),
        "region_name": str(region["region_name"]),
        "administrative_type": str(region["administrative_type"]),
    }


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
