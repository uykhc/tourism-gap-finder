"""기초지자체 중심 관광지 상위 목록 CLI."""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

from ..tourism_data.config import resolve_hub_service_key
from .hub_api import HubTourApiClient, HubTourApiError
from .hub_output import write_hub_csv, write_hub_json
from .models import HubTouristSpotReport


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="기초지자체 중심 관광지 순위에서 상위 5개를 추출합니다."
    )
    parser.add_argument("--region-name", required=True, help="결과에 표시할 지역명")
    parser.add_argument(
        "--base-ym",
        required=True,
        type=_year_month,
        help="조회 기준월(YYYYMM)",
    )
    parser.add_argument(
        "--area-code",
        required=True,
        help="중심 관광지 API의 시도 코드(행정표준코드)",
    )
    parser.add_argument(
        "--sigungu-code",
        required=True,
        help="중심 관광지 API의 5자리 시군구 코드(행정표준코드)",
    )
    parser.add_argument(
        "--limit",
        type=_positive_int,
        default=5,
        help="추출 개수(기본값: 5)",
    )
    parser.add_argument(
        "--service-key",
        help=(
            "중심 관광지 API 인증키(기본값: HUB_TOUR_API_SERVICE_KEY, "
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
            args.service_key = resolve_hub_service_key()
        except (OSError, ValueError) as exc:
            print(f"오류: {exc}", file=sys.stderr)
            return 2
    if not args.service_key:
        parser.error(
            "--service-key, HUB_TOUR_API_SERVICE_KEY 또는 "
            "TOUR_API_SERVICE_KEY로 인증키를 입력해야 합니다."
        )

    try:
        client = HubTourApiClient(
            args.service_key,
            timeout_seconds=args.timeout,
        )
        spots = client.fetch_top_spots(
            base_year_month=args.base_ym,
            area_code=args.area_code,
            sigungu_code=args.sigungu_code,
            limit=args.limit,
        )
        report = HubTouristSpotReport(
            region_name=args.region_name,
            base_year_month=args.base_ym,
            area_code=str(args.area_code),
            sigungu_code=str(args.sigungu_code),
            limit=args.limit,
            spots=tuple(spots),
        )
        written_paths = _write_outputs(
            report,
            output_dir=args.output_dir,
            output_format=args.format,
        )
    except (HubTourApiError, OSError, ValueError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 1

    _print_summary(report)
    for path in written_paths:
        print(f"저장: {path}")
    return 0


def _write_outputs(
    report: HubTouristSpotReport,
    *,
    output_dir: Path,
    output_format: str,
) -> list[Path]:
    safe_region = _safe_file_name(report.region_name)
    file_stem = (
        f"{safe_region}_hub_top{report.limit}_{report.base_year_month}"
    )
    written: list[Path] = []
    if output_format in ("json", "both"):
        written.append(
            write_hub_json(report, output_dir / f"{file_stem}.json")
        )
    if output_format in ("csv", "both"):
        written.append(
            write_hub_csv(report, output_dir / f"{file_stem}.csv")
        )
    return written


def _print_summary(report: HubTouristSpotReport) -> None:
    print(
        f"{report.region_name} {report.base_year_month}: "
        f"중심 관광지 {len(report.spots)}개"
    )
    print(f"{'순위':>4}  {'관광지명':<30} {'관광지코드':<16}")
    for spot in report.spots:
        print(f"{spot.rank:>4}  {spot.name:<30} {spot.tourist_spot_code:<16}")


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
