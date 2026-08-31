"""경기도 중심 관광지 벤치마크 배치 분석 CLI."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from .benchmark import (
    BenchmarkRegionResult,
    BenchmarkRunReport,
    build_distributions,
    load_benchmark_config,
    validate_tour_region_codes,
)
from .benchmark_output import (
    write_benchmark_anchor_csv,
    write_benchmark_distribution_csv,
    write_benchmark_failure_csv,
    write_benchmark_json,
)
from hankkeut_calculation.tourism_data.config import resolve_hub_service_key, resolve_portfolio_service_key
from hankkeut_calculation.gap_analyzer.hub_api import HubTourApiClient, HubTourApiError
from hankkeut_calculation.gap_analyzer.stay_analysis import analyze_stay_transition
from hankkeut_calculation.gap_analyzer.stay_models import StayTransitionReport
from hankkeut_calculation.gap_analyzer.stay_output import (
    write_stay_anchor_csv,
    write_stay_json,
    write_stay_summary_csv,
)
from hankkeut_calculation.gap_analyzer.tour_api import TourApiClient, TourApiError

DEFAULT_CONFIG_PATH = Path("config/gyeonggi/anchor_benchmark.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "설정 파일의 여러 지역을 순회하며 중심 관광지 체류 보완 "
            "벤치마크를 수집합니다."
        )
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"벤치마크 설정 JSON(기본값: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--tour-service-key",
        help="KorService2 인증키(기본값: KOR_TOUR_API_SERVICE_KEY)",
    )
    parser.add_argument(
        "--hub-service-key",
        help="중심 관광지 API 인증키(기본값: HUB_TOUR_API_SERVICE_KEY)",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/benchmarks"),
        help="결과 디렉터리(기본값: results/benchmarks)",
    )
    parser.add_argument(
        "--page-size",
        type=_positive_int,
        default=1000,
        help="KorService2 페이지당 조회 건수(기본값: 1000)",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=30.0,
        help="API별 호출 제한 시간(초, 기본값: 30)",
    )
    parser.add_argument(
        "--fail-fast",
        action="store_true",
        help="지역 하나가 실패하면 즉시 중단",
    )
    parser.add_argument(
        "--validate-only",
        action="store_true",
        help="공식 KorService2 시군구 코드만 검증하고 종료",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_benchmark_config(args.config)
        # 경기도 군은 이번 시 전용 선정에서 표본 부족으로 수집·가공하지 않는다.
        active_regions = tuple(region for region in config.regions if region.sample_group == "시")
        tour_service_key = (
            args.tour_service_key or resolve_portfolio_service_key()
        )
        hub_service_key = args.hub_service_key or resolve_hub_service_key()
    except (OSError, ValueError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    if not tour_service_key:
        parser.error("KOR_TOUR_API_SERVICE_KEY를 입력해야 합니다.")
    if not hub_service_key:
        parser.error("HUB_TOUR_API_SERVICE_KEY를 입력해야 합니다.")

    generated_at = datetime.now(timezone.utc).isoformat()
    hub_client = HubTourApiClient(
        hub_service_key,
        timeout_seconds=args.timeout,
    )
    tour_client = TourApiClient(
        tour_service_key,
        timeout_seconds=args.timeout,
        page_size=args.page_size,
    )
    try:
        codes_by_area = {
            area_code: tour_client.fetch_sigungu_codes(area_code=area_code)
            for area_code in sorted(
                {region.tour_area_code for region in active_regions}
            )
        }
    except (TourApiError, OSError, ValueError) as exc:
        print(f"지역 코드 검증 실패: {exc}", file=sys.stderr)
        return 2
    code_errors = validate_tour_region_codes(
        active_regions,
        codes_by_area,
    )
    if code_errors:
        print("KorService2 지역 코드 설정이 올바르지 않습니다.", file=sys.stderr)
        for error in code_errors:
            print(f"- {error}", file=sys.stderr)
        return 2
    print(
        f"KorService2 지역 코드 검증 완료: {len(active_regions)}개 시",
        flush=True,
    )
    if args.validate_only:
        return 0

    successful: list[BenchmarkRegionResult] = []
    failures: list[tuple[str, str]] = []

    for index, definition in enumerate(active_regions, start=1):
        print(
            f"[{index}/{len(active_regions)}] {definition.region_name} 조회 중...",
            flush=True,
        )
        try:
            hubs = hub_client.fetch_top_spots(
                base_year_month=config.base_year_month,
                area_code=definition.hub_area_code,
                sigungu_code=definition.hub_sigungu_code,
                limit=config.anchor_count_per_region,
                category_large=config.hub_category_large,
                category_middle=config.hub_category_middle,
                excluded_category_middle=(
                    config.excluded_hub_category_middle
                ),
            )
            if len(hubs) < config.anchor_count_per_region:
                raise ValueError(
                    f"중심 관광지가 {len(hubs)}개만 조회됐습니다 "
                    f"(요청 {config.anchor_count_per_region}개)."
                )
            resources = tour_client.fetch_region_resources(
                area_code=definition.tour_area_code,
                sigungu_code=definition.tour_sigungu_code,
            )
            if not resources:
                raise ValueError("KorService2 관광자원이 0개입니다.")
            report = analyze_stay_transition(
                hubs,
                resources,
                region_name=definition.region_name,
                generated_at=generated_at,
                hub_base_year_month=config.base_year_month,
                hub_area_code=definition.hub_area_code,
                hub_sigungu_code=definition.hub_sigungu_code,
                tour_area_code=definition.tour_area_code,
                tour_sigungu_code=definition.tour_sigungu_code,
                requested_anchor_count=config.anchor_count_per_region,
                radii_km=config.radii_km,
            )
            _write_region_outputs(
                report,
                args.output_dir / "regions" / config.output_slug,
            )
            successful.append(
                BenchmarkRegionResult(definition=definition, report=report)
            )
            names = ", ".join(anchor.name for anchor in report.anchors)
            print(
                f"[{index}/{len(active_regions)}] {definition.region_name} 완료: "
                f"{names}",
                flush=True,
            )
        except (HubTourApiError, TourApiError, OSError, ValueError) as exc:
            message = str(exc)
            failures.append((definition.region_name, message))
            print(
                f"[{index}/{len(active_regions)}] {definition.region_name} 실패: "
                f"{message}",
                file=sys.stderr,
                flush=True,
            )
            if args.fail_fast:
                break

    region_results = tuple(successful)
    distributions = build_distributions(
        region_results,
        radii_km=config.radii_km,
    )
    run_report = BenchmarkRunReport(
        benchmark_name=config.benchmark_name,
        generated_at=generated_at,
        base_year_month=config.base_year_month,
        anchor_count_per_region=config.anchor_count_per_region,
        hub_category_large=config.hub_category_large,
        excluded_hub_category_middle=(
            config.excluded_hub_category_middle
        ),
        radii_km=config.radii_km,
        region_results=region_results,
        distributions=distributions,
        failures=tuple(failures),
        hub_category_middle=config.hub_category_middle,
        output_slug=config.output_slug,
    )
    written = _write_combined_outputs(run_report, args.output_dir)
    print(
        f"완료: 성공 {len(successful)}개 지역, 실패 {len(failures)}개 지역",
        flush=True,
    )
    for path in written:
        print(f"저장: {path}", flush=True)
    return 1 if failures else 0


def _write_region_outputs(
    report: StayTransitionReport,
    output_dir: Path,
) -> None:
    file_stem = (
        f"{_safe_file_name(report.region_name)}_stay_transition_"
        f"{report.hub_base_year_month}"
    )
    write_stay_json(report, output_dir / f"{file_stem}.json")
    write_stay_anchor_csv(report, output_dir / f"{file_stem}.csv")
    write_stay_summary_csv(
        report,
        output_dir / f"{file_stem}_summary.csv",
    )


def _write_combined_outputs(
    report: BenchmarkRunReport,
    output_dir: Path,
) -> list[Path]:
    file_stem = f"{report.output_slug}_{report.base_year_month}"
    paths = [
        write_benchmark_json(report, output_dir / f"{file_stem}.json"),
        write_benchmark_anchor_csv(
            report,
            output_dir / f"{file_stem}_anchors.csv",
        ),
        write_benchmark_distribution_csv(
            report,
            output_dir / f"{file_stem}_distributions.csv",
        ),
        write_benchmark_failure_csv(
            report,
            output_dir / f"{file_stem}_failures.csv",
        ),
    ]
    return paths


def _safe_file_name(value: str) -> str:
    cleaned = re.sub(r"[^\w.-]+", "_", value.strip(), flags=re.UNICODE)
    return cleaned.strip("._") or "region"


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("정수를 입력해야 합니다.") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("0보다 큰 정수를 입력해야 합니다.")
    return parsed


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("숫자를 입력해야 합니다.") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("0보다 큰 값을 입력해야 합니다.")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
