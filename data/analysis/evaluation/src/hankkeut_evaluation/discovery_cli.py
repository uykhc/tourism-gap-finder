"""중심 관광지 실제 중분류 후보 탐색 CLI."""

from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

from .benchmark import load_benchmark_config
from hankkeut_calculation.tourism_data.config import resolve_hub_service_key
from hankkeut_calculation.gap_analyzer.hub_api import HubTourApiClient, HubTourApiError

DEFAULT_CONFIG_PATH = Path("config/gyeonggi/anchor_benchmark.json")
DEFAULT_CATEGORIES = ("자연관광", "레저스포츠", "기타관광")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="지역별 중심 관광지 중분류 후보와 개수를 조사합니다."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"지역 설정 JSON(기본값: {DEFAULT_CONFIG_PATH})",
    )
    parser.add_argument(
        "--category-middle",
        action="append",
        dest="categories",
        help="조사할 실제 중분류(여러 번 지정 가능)",
    )
    parser.add_argument(
        "--hub-service-key",
        help="중심 관광지 API 인증키(기본값: HUB_TOUR_API_SERVICE_KEY)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(
            "results/benchmarks/gyeonggi_hub_category_inventory_202503.csv"
        ),
        help="후보 CSV 경로",
    )
    parser.add_argument(
        "--timeout",
        type=_positive_float,
        default=30.0,
        help="API 호출 제한 시간(초, 기본값: 30)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        config = load_benchmark_config(args.config)
        service_key = args.hub_service_key or resolve_hub_service_key()
    except (OSError, ValueError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2
    if not service_key:
        parser.error("HUB_TOUR_API_SERVICE_KEY를 입력해야 합니다.")

    categories = tuple(dict.fromkeys(args.categories or DEFAULT_CATEGORIES))
    client = HubTourApiClient(service_key, timeout_seconds=args.timeout)
    # 경기도 군은 이번 시 전용 선정에서 표본 부족으로 수집·가공하지 않는다.
    active_regions = tuple(region for region in config.regions if region.sample_group == "시")
    rows: list[dict[str, object]] = []
    failures: list[tuple[str, str]] = []

    for index, region in enumerate(active_regions, start=1):
        try:
            spots = client.fetch_top_spots(
                base_year_month=config.base_year_month,
                area_code=region.hub_area_code,
                sigungu_code=region.hub_sigungu_code,
                limit=100,
                category_large=config.hub_category_large,
            )
            selected = [
                spot for spot in spots if spot.category_middle in categories
            ]
            for spot in selected:
                rows.append(
                    {
                        "base_year_month": config.base_year_month,
                        "province_name": region.province_name,
                        "region_name": region.region_name,
                        "sampling_stratum": region.sample_group,
                        "rank": spot.rank,
                        "tourist_spot_code": spot.tourist_spot_code,
                        "name": spot.name,
                        "category_large": spot.category_large,
                        "category_middle": spot.category_middle,
                        "category_small": spot.category_small,
                        "longitude": spot.longitude,
                        "latitude": spot.latitude,
                    }
                )
            counts = Counter(spot.category_middle for spot in selected)
            summary = ", ".join(
                f"{category} {counts[category]}개" for category in categories
            )
            print(
                f"[{index}/{len(active_regions)}] {region.region_name}: {summary}",
                flush=True,
            )
        except (HubTourApiError, OSError, ValueError) as exc:
            failures.append((region.region_name, str(exc)))
            print(
                f"[{index}/{len(active_regions)}] {region.region_name} 실패: {exc}",
                file=sys.stderr,
                flush=True,
            )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "base_year_month",
        "province_name",
        "region_name",
        "sampling_stratum",
        "rank",
        "tourist_spot_code",
        "name",
        "category_large",
        "category_middle",
        "category_small",
        "longitude",
        "latitude",
    ]
    with args.output.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    totals = Counter(str(row["category_middle"]) for row in rows)
    print(f"저장: {args.output}")
    print(
        "전체 후보: "
        + ", ".join(f"{category} {totals[category]}개" for category in categories)
    )
    return 1 if failures else 0


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
