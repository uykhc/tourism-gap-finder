"""관광자원 포트폴리오 분석 CLI."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from .analysis import analyze_portfolio
from ..tourism_data.config import resolve_portfolio_service_key
from .models import PortfolioReport
from .output import write_csv, write_json
from .tour_api import TourApiClient, TourApiError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "TourAPI 시군구 관광자원을 유형별 구성비와 "
            "단위면적당 개수로 분석합니다."
        )
    )
    parser.add_argument("--region-name", required=True, help="결과에 표시할 시군구명")
    parser.add_argument("--area-code", required=True, help="TourAPI 광역시도 코드")
    parser.add_argument(
        "--sigungu-code",
        help="TourAPI 시군구 코드(생략 시 광역시·도 전체)",
    )
    parser.add_argument(
        "--area-km2",
        required=True,
        type=_positive_float,
        help="시군구 행정구역 면적(km²)",
    )
    parser.add_argument(
        "--service-key",
        help=(
            "KorService2 인증키(기본값: KOR_TOUR_API_SERVICE_KEY, "
            "대체값: TOUR_API_SERVICE_KEY)"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("results"),
        help="결과 디렉터리(기본값: results)",
    )
    parser.add_argument(
        "--format",
        choices=("json", "csv", "both"),
        default="both",
        help="저장 형식(기본값: both)",
    )
    parser.add_argument(
        "--page-size",
        type=_positive_int,
        default=1000,
        help="TourAPI 페이지당 조회 건수(기본값: 1000)",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=20.0,
        help="API 호출 제한 시간(초, 기본값: 20)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not args.service_key:
        try:
            args.service_key = resolve_portfolio_service_key()
        except (OSError, ValueError) as exc:
            print(f"오류: {exc}", file=sys.stderr)
            return 2
    if not args.service_key:
        parser.error(
            "--service-key, KOR_TOUR_API_SERVICE_KEY 또는 "
            "TOUR_API_SERVICE_KEY로 인증키를 입력해야 합니다."
        )

    try:
        client = TourApiClient(
            args.service_key,
            timeout_seconds=args.timeout,
            page_size=args.page_size,
        )
        resources = client.fetch_region_resources(
            area_code=args.area_code,
            sigungu_code=args.sigungu_code,
        )
        report = analyze_portfolio(
            resources,
            region_name=args.region_name,
            area_code=args.area_code,
            sigungu_code=args.sigungu_code,
            area_square_km=args.area_km2,
        )
        written_paths = _write_outputs(
            report,
            output_dir=args.output_dir,
            output_format=args.format,
        )
    except (TourApiError, OSError, ValueError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1

    _print_summary(report)
    for path in written_paths:
        print(f"저장: {path}")
    return 0


def _write_outputs(
    report: PortfolioReport,
    *,
    output_dir: Path,
    output_format: str,
) -> list[Path]:
    file_stem = f"{_safe_file_name(report.region_name)}_portfolio"
    written: list[Path] = []
    if output_format in ("json", "both"):
        written.append(write_json(report, output_dir / f"{file_stem}.json"))
    if output_format in ("csv", "both"):
        written.append(write_csv(report, output_dir / f"{file_stem}.csv"))
    return written


def _print_summary(report: PortfolioReport) -> None:
    print(
        f"{report.region_name}: 총 {report.total_resource_count}개, "
        f"{report.total_count_per_square_km:.4f}개/km²"
    )
    print(f"{'유형':<14} {'개수':>7} {'구성비(%)':>12} {'개/km²':>12}")
    for metric in report.metrics:
        print(
            f"{metric.content_type_name:<14} "
            f"{metric.count:>7d} "
            f"{metric.percentage:>12.4f} "
            f"{metric.count_per_square_km:>12.4f}"
        )


def _safe_file_name(value: str) -> str:
    cleaned = re.sub(r"[^\w.-]+", "_", value.strip(), flags=re.UNICODE)
    return cleaned.strip("._") or "region"


def _positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("숫자를 입력해야 합니다.") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("0보다 큰 값을 입력해야 합니다.")
    return parsed


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("정수를 입력해야 합니다.") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("0보다 큰 정수를 입력해야 합니다.")
    return parsed


if __name__ == "__main__":
    raise SystemExit(main())
