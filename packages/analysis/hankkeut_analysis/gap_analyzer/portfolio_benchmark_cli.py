"""경기도 포트폴리오 밀도 벤치마크 배치 CLI."""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from .analysis import analyze_portfolio
from ..tourism_data.config import resolve_portfolio_service_key
from .output import write_csv, write_json
from .portfolio_benchmark import (
    PortfolioBenchmarkRegionResult,
    PortfolioBenchmarkRunReport,
    build_portfolio_distributions,
    load_portfolio_benchmark_config,
    validate_portfolio_region_codes,
)
from .portfolio_benchmark_output import (
    write_portfolio_benchmark_json,
    write_portfolio_distribution_csv,
    write_portfolio_failure_csv,
    write_portfolio_region_csv,
)
from .tour_api import TourApiClient, TourApiError

DEFAULT_CONFIG_PATH = Path("config/gyeonggi/portfolio_benchmark.json")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="경기도 시의 유형별 관광자원 밀도 분포를 계산합니다."
    )
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--service-key", help="KorService2 인증키")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results/portfolio_benchmarks"),
    )
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--timeout", type=float, default=30.0)
    parser.add_argument("--validate-only", action="store_true")
    parser.add_argument("--fail-fast", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        config = load_portfolio_benchmark_config(args.config)
        # 경기도 군은 이번 시 전용 선정에서 표본 부족으로 수집·가공하지 않는다.
        active_regions = tuple(
            region for region in config.regions if region.administrative_type == "city"
        )
        service_key = args.service_key or resolve_portfolio_service_key()
        if not service_key:
            raise ValueError("KOR_TOUR_API_SERVICE_KEY를 입력해야 합니다.")
        client = TourApiClient(
            service_key,
            timeout_seconds=args.timeout,
            page_size=args.page_size,
        )
        codes_by_area = {
            area_code: client.fetch_sigungu_codes(area_code=area_code)
            for area_code in sorted({item.area_code for item in active_regions})
        }
    except (OSError, TourApiError, ValueError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    code_errors = validate_portfolio_region_codes(active_regions, codes_by_area)
    if code_errors:
        print("TourAPI 지역 코드 설정이 올바르지 않습니다.", file=sys.stderr)
        for error in code_errors:
            print(f"- {error}", file=sys.stderr)
        return 2
    print(f"TourAPI 지역 코드 검증 완료: {len(active_regions)}개 시", flush=True)
    if args.validate_only:
        return 0

    generated_at = datetime.now(timezone.utc).isoformat()
    successful: list[PortfolioBenchmarkRegionResult] = []
    failures: list[tuple[str, str]] = []
    for index, definition in enumerate(active_regions, start=1):
        label = f"{definition.province_name} {definition.region_name}"
        print(f"[{index}/{len(active_regions)}] {label} 조회 중...", flush=True)
        try:
            resources = client.fetch_region_resources(
                area_code=definition.area_code,
                sigungu_code=definition.sigungu_code,
            )
            report = analyze_portfolio(
                resources,
                region_name=definition.region_name,
                area_code=definition.area_code,
                sigungu_code=definition.sigungu_code,
                area_square_km=definition.area_square_km,
            )
            region_dir = args.output_dir / "regions" / config.output_slug
            write_json(report, region_dir / f"{definition.province_name}_{definition.region_name}.json")
            write_csv(report, region_dir / f"{definition.province_name}_{definition.region_name}.csv")
            successful.append(
                PortfolioBenchmarkRegionResult(definition=definition, report=report)
            )
            print(
                f"[{index}/{len(active_regions)}] {label} 완료: "
                f"{report.total_resource_count}개",
                flush=True,
            )
        except (OSError, TourApiError, ValueError) as exc:
            failures.append((label, str(exc)))
            print(f"[{index}/{len(active_regions)}] {label} 실패: {exc}", file=sys.stderr)
            if args.fail_fast:
                break

    region_results = tuple(successful)
    distributions = build_portfolio_distributions(region_results)
    report = PortfolioBenchmarkRunReport(
        benchmark_name=config.benchmark_name,
        output_slug=config.output_slug,
        generated_at=generated_at,
        area_reference_date=config.area_reference_date,
        area_source_url=config.area_source_url,
        region_results=region_results,
        distributions=distributions,
        failures=tuple(failures),
    )
    date_stamp = generated_at[:10].replace("-", "")
    stem = f"{config.output_slug}_{date_stamp}"
    written = [
        write_portfolio_benchmark_json(report, args.output_dir / f"{stem}.json"),
        write_portfolio_region_csv(report, args.output_dir / f"{stem}_regions.csv"),
        write_portfolio_distribution_csv(
            report, args.output_dir / f"{stem}_distributions.csv"
        ),
        write_portfolio_failure_csv(
            report, args.output_dir / f"{stem}_failures.csv"
        ),
    ]
    print(f"완료: 성공 {len(successful)}개, 실패 {len(failures)}개", flush=True)
    for path in written:
        print(f"저장: {path}", flush=True)
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
