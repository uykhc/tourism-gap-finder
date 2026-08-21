"""체류 전환 빈칸 분석 CLI."""

from __future__ import annotations

import argparse
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from ..tourism_data.config import resolve_hub_service_key, resolve_portfolio_service_key
from .hub_api import HubTourApiClient, HubTourApiError
from .stay_analysis import analyze_stay_transition
from .stay_models import StayTransitionReport
from .stay_output import (
    write_stay_anchor_csv,
    write_stay_json,
    write_stay_summary_csv,
)
from .tour_api import TourApiClient, TourApiError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "중심 관광지 주변의 음식점·숙박·문화시설·행사·쇼핑을 "
            "반경별로 분석합니다."
        )
    )
    parser.add_argument("--region-name", required=True, help="결과에 표시할 지역명")
    parser.add_argument(
        "--base-ym",
        required=True,
        type=_year_month,
        help="중심 관광지 순위 기준월(YYYYMM)",
    )
    parser.add_argument(
        "--hub-area-code",
        required=True,
        help="중심 관광지 API 시도 코드(예: 경상북도 47)",
    )
    parser.add_argument(
        "--hub-sigungu-code",
        required=True,
        help="중심 관광지 API 5자리 시군구 코드(예: 경주시 47130)",
    )
    parser.add_argument(
        "--tour-area-code",
        required=True,
        help="KorService2 광역시도 코드(예: 경상북도 35)",
    )
    parser.add_argument(
        "--tour-sigungu-code",
        required=True,
        help="KorService2 시군구 코드(예: 경주시 2)",
    )
    parser.add_argument(
        "--anchor-count",
        type=_anchor_count,
        default=5,
        help="대표 관광지 수(1~100, 기본값: 5)",
    )
    parser.add_argument(
        "--hub-category-large",
        default="관광지",
        help="중심 관광지 대분류 필터(기본값: 관광지)",
    )
    parser.add_argument(
        "--exclude-hub-category-middle",
        action="append",
        help="제외할 중심 관광지 중분류(여러 번 지정 가능; 기본값: 쇼핑)",
    )
    parser.add_argument(
        "--radius-km",
        action="append",
        type=_positive_float,
        dest="radii_km",
        help="분석 반경(km, 여러 번 지정 가능; 기본값: 1, 2)",
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
        help="KorService2 페이지당 조회 건수(기본값: 1000)",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=20.0,
        help="API별 호출 제한 시간(초, 기본값: 20)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        tour_service_key = (
            args.tour_service_key or resolve_portfolio_service_key()
        )
        hub_service_key = args.hub_service_key or resolve_hub_service_key()
    except (OSError, ValueError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    if not tour_service_key:
        parser.error(
            "--tour-service-key 또는 KOR_TOUR_API_SERVICE_KEY로 "
            "KorService2 인증키를 입력해야 합니다."
        )
    if not hub_service_key:
        parser.error(
            "--hub-service-key 또는 HUB_TOUR_API_SERVICE_KEY로 "
            "중심 관광지 API 인증키를 입력해야 합니다."
        )

    try:
        hubs = HubTourApiClient(
            hub_service_key,
            timeout_seconds=args.timeout,
        ).fetch_top_spots(
            base_year_month=args.base_ym,
            area_code=args.hub_area_code,
            sigungu_code=args.hub_sigungu_code,
            limit=args.anchor_count,
            category_large=args.hub_category_large,
            excluded_category_middle=(
                args.exclude_hub_category_middle or ("쇼핑",)
            ),
        )
        resources = TourApiClient(
            tour_service_key,
            timeout_seconds=args.timeout,
            page_size=args.page_size,
        ).fetch_region_resources(
            area_code=args.tour_area_code,
            sigungu_code=args.tour_sigungu_code,
        )
        report = analyze_stay_transition(
            hubs,
            resources,
            region_name=args.region_name,
            generated_at=datetime.now(timezone.utc).isoformat(),
            hub_base_year_month=args.base_ym,
            hub_area_code=args.hub_area_code,
            hub_sigungu_code=args.hub_sigungu_code,
            tour_area_code=args.tour_area_code,
            tour_sigungu_code=args.tour_sigungu_code,
            requested_anchor_count=args.anchor_count,
            radii_km=args.radii_km or (1.0, 2.0),
        )
        written_paths = _write_outputs(
            report,
            output_dir=args.output_dir,
            output_format=args.format,
        )
    except (HubTourApiError, TourApiError, OSError, ValueError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1

    _print_summary(report)
    for path in written_paths:
        print(f"저장: {path}")
    return 0


def _write_outputs(
    report: StayTransitionReport,
    *,
    output_dir: Path,
    output_format: str,
) -> list[Path]:
    file_stem = (
        f"{_safe_file_name(report.region_name)}_stay_transition_"
        f"{report.hub_base_year_month}"
    )
    written: list[Path] = []
    if output_format in ("json", "both"):
        written.append(
            write_stay_json(report, output_dir / f"{file_stem}.json")
        )
    if output_format in ("csv", "both"):
        written.append(
            write_stay_anchor_csv(report, output_dir / f"{file_stem}.csv")
        )
        written.append(
            write_stay_summary_csv(
                report,
                output_dir / f"{file_stem}_summary.csv",
            )
        )
    return written


def _print_summary(report: StayTransitionReport) -> None:
    print(
        f"{report.region_name}: 대표 관광지 {report.analyzed_anchor_count}개, "
        f"TourAPI 자원 {report.total_tourism_resource_count}개 "
        f"(좌표 보유 {report.geocoded_tourism_resource_count}개)"
    )
    print(
        f"{'관광지':<24} {'반경(km)':>8} {'음식':>6} {'숙박':>6} "
        f"{'문화':>6} {'행사':>6} {'쇼핑':>6} {'점수':>8}"
    )
    for anchor in report.anchors:
        for radius in anchor.radii:
            counts = {count.key: count.count for count in radius.counts}
            print(
                f"{anchor.name:<24} {radius.radius_km:>8g} "
                f"{counts['food']:>6} {counts['accommodation']:>6} "
                f"{counts['culture']:>6} {counts['event']:>6} "
                f"{counts['shopping']:>6} "
                f"{radius.complement_coverage_score:>8.1f}"
            )
    for summary in report.regional_summaries:
        print(
            f"지역 평균 {summary.radius_km:g}km: "
            f"{summary.average_complement_coverage_score:.1f}점, "
            f"고유 자원 {summary.unique_complement_resource_count}개, "
            f"중첩 집계 {summary.overlap_occurrence_count}건"
        )


def _safe_file_name(value: str) -> str:
    cleaned = re.sub(r"[^\w.-]+", "_", value.strip(), flags=re.UNICODE)
    return cleaned.strip("._") or "region"


def _year_month(value: str) -> str:
    if not re.fullmatch(r"\d{6}", value):
        raise argparse.ArgumentTypeError("YYYYMM 형식으로 입력해야 합니다.")
    if not 1 <= int(value[4:]) <= 12:
        raise argparse.ArgumentTypeError("월은 01부터 12까지 입력해야 합니다.")
    return value


def _positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("정수를 입력해야 합니다.") from exc
    if parsed <= 0:
        raise argparse.ArgumentTypeError("0보다 큰 정수를 입력해야 합니다.")
    return parsed


def _anchor_count(value: str) -> int:
    parsed = _positive_int(value)
    if parsed > 100:
        raise argparse.ArgumentTypeError("100 이하로 입력해야 합니다.")
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
