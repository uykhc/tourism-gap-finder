"""이동통신 기반 방문자 수 상위 지역의 포트폴리오 기준을 계산한다."""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import resolve_visitor_service_key
from .portfolio_benchmark import (
    build_portfolio_distributions,
    portfolio_region_result_from_dict,
)
from .visitor_api import DailyRegionalVisitor, VisitorApiClient, VisitorApiError
from .tourism_demand_api import (
    TourismDemandApiClient,
    TourismDemandApiError,
    TourismDemandRecord,
    previous_months,
)

DEFAULT_CONFIG_PATH = Path("config/gyeonggi_visitor_portfolio_benchmark.json")
DEFAULT_OUTPUT_DIR = Path("results/portfolio_benchmarks")

# 경기도 군(연천·가평·양평)은 표본이 3개뿐이므로 이번 선정·수집에서는 제외한다.
# 이후 전국 군 비교군을 확보하면 이 목록과 별도로 군 매핑을 다시 활성화한다.
ACTIVE_CITY_SIGUNGU_CODES: dict[str, tuple[str, ...]] = {
    "수원시": ("41111", "41113", "41115", "41117"),
    "성남시": ("41131", "41133", "41135"),
    "의정부시": ("41150",), "안양시": ("41171", "41173"),
    "부천시": ("41192", "41194", "41196"), "광명시": ("41210",),
    "평택시": ("41220",), "동두천시": ("41250",),
    "안산시": ("41271", "41273"), "고양시": ("41281", "41285", "41287"),
    "과천시": ("41290",), "구리시": ("41310",), "남양주시": ("41360",),
    "오산시": ("41370",), "시흥시": ("41390",), "군포시": ("41410",),
    "의왕시": ("41430",), "하남시": ("41450",),
    "용인시": ("41461", "41463", "41465"), "파주시": ("41480",),
    "이천시": ("41500",), "안성시": ("41550",), "김포시": ("41570",),
    "화성시": ("41590",), "광주시": ("41610",), "양주시": ("41630",),
    "포천시": ("41650",), "여주시": ("41670",),
}


@dataclass(frozen=True, slots=True)
class VisitorPortfolioConfig:
    benchmark_name: str
    output_slug: str
    start_ymd: str
    end_ymd: str
    top_region_count: int
    source_url: str
    visitor_type_names: tuple[str, ...]
    demand_area_code: str
    demand_lookback_months: int
    visitor_weight: float
    resource_demand_weight: float
    demand_intensity_weight: float


@dataclass(frozen=True, slots=True)
class CityTourismScore:
    region_name: str
    visitor_sum: float
    resource_demand: float
    demand_intensity: float
    visitor_percentile: float
    resource_demand_percentile: float
    demand_intensity_percentile: float
    composite_score: float

    def to_dict(self) -> dict[str, float | str]:
        return {key: getattr(self, key) for key in self.__dataclass_fields__}


def load_visitor_config(path: Path) -> VisitorPortfolioConfig:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"방문자 수 벤치마크 설정 파일이 없습니다: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"방문자 수 벤치마크 설정 JSON 형식이 올바르지 않습니다: {exc}") from exc
    required = ("benchmark_name", "output_slug", "start_ymd", "end_ymd", "source_url")
    missing = [key for key in required if not str(value.get(key, "")).strip()]
    if missing:
        raise ValueError("방문자 수 설정 필수 항목 누락: " + ", ".join(missing))
    output_slug = str(value["output_slug"]).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", output_slug):
        raise ValueError("output_slug 형식이 올바르지 않습니다.")
    try:
        top_region_count = int(value.get("top_region_count"))
    except (TypeError, ValueError) as exc:
        raise ValueError("top_region_count는 정수여야 합니다.") from exc
    if top_region_count < 1:
        raise ValueError("top_region_count는 1 이상이어야 합니다.")
    raw_types = value.get("visitor_type_names", [])
    if not isinstance(raw_types, list) or not all(isinstance(item, str) for item in raw_types):
        raise ValueError("visitor_type_names는 문자열 배열이어야 합니다.")
    source_url = str(value["source_url"]).strip()
    if not source_url.startswith("https://"):
        raise ValueError("source_url은 https:// 주소여야 합니다.")
    weights = value.get("weights", {})
    if not isinstance(weights, dict):
        raise ValueError("weights는 객체여야 합니다.")
    try:
        visitor_weight = float(weights.get("visitor", 0.4))
        resource_demand_weight = float(weights.get("resource_demand", 0.3))
        demand_intensity_weight = float(weights.get("demand_intensity", 0.3))
    except (TypeError, ValueError) as exc:
        raise ValueError("weights 값은 숫자여야 합니다.") from exc
    if round(visitor_weight + resource_demand_weight + demand_intensity_weight, 9) != 1:
        raise ValueError("weights의 합은 1이어야 합니다.")
    demand_lookback_months = int(value.get("demand_lookback_months", 24))
    if demand_lookback_months < 1:
        raise ValueError("demand_lookback_months는 1 이상이어야 합니다.")
    return VisitorPortfolioConfig(
        benchmark_name=str(value["benchmark_name"]).strip(),
        output_slug=output_slug,
        start_ymd=str(value["start_ymd"]).strip(),
        end_ymd=str(value["end_ymd"]).strip(),
        top_region_count=top_region_count,
        source_url=source_url,
        visitor_type_names=tuple(item.strip() for item in raw_types if item.strip()),
        demand_area_code=str(value.get("demand_area_code", "41")).strip(),
        demand_lookback_months=demand_lookback_months,
        visitor_weight=visitor_weight,
        resource_demand_weight=resource_demand_weight,
        demand_intensity_weight=demand_intensity_weight,
    )


def aggregate_daily_visitor_sums(
    records: list[DailyRegionalVisitor],
    *,
    allowed_region_names: set[str],
    visitor_type_names: tuple[str, ...] = (),
) -> tuple[list[dict[str, Any]], set[str]]:
    """동일 기간의 일별 방문자 수를 지역별로 더한다.

    이 값은 기간 내 고유 개인 수가 아니라 ``일별 순방문자 수의 합``이다.
    """
    selected_types = set(visitor_type_names)
    totals: dict[str, float] = {}
    seen_names: set[str] = set()
    for record in records:
        if record.region_name not in allowed_region_names:
            continue
        if selected_types and record.visitor_type not in selected_types:
            continue
        seen_names.add(record.region_name)
        totals[record.region_name] = totals.get(record.region_name, 0.0) + record.visitor_count
    rows = [
        {"region_name": name, "daily_visitor_sum": round(total, 2)}
        for name, total in totals.items()
    ]
    rows.sort(key=lambda row: (-float(row["daily_visitor_sum"]), str(row["region_name"])))
    for rank, row in enumerate(rows, start=1):
        row["visitor_rank"] = rank
    return rows, seen_names


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="경기도 시의 방문자·관광 수요 지수로 우수 관광 지역을 선정합니다."
    )
    parser.add_argument("--input", type=Path, help="전체 포트폴리오 벤치마크 JSON")
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG_PATH)
    parser.add_argument("--service-key", help="방문자 수 API 인증키")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--page-size", type=int, default=1000)
    parser.add_argument("--timeout", type=float, default=30.0)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        input_path = _resolve_input_path(args.input, args.output_dir)
        config = load_visitor_config(args.config)
        service_key = args.service_key or resolve_visitor_service_key()
        if not service_key:
            raise ValueError("VISITOR_API_SERVICE_KEY를 입력해야 합니다.")
        payload = json.loads(input_path.read_text(encoding="utf-8"))
        all_results = tuple(portfolio_region_result_from_dict(item) for item in payload["region_results"])
        # 군 데이터는 이번 시 전용 분석에서 수집·가공하지 않는다.
        city_results = tuple(
            item for item in all_results if item.definition.administrative_type == "city"
        )
        if set(item.definition.region_name for item in city_results) != set(ACTIVE_CITY_SIGUNGU_CODES):
            raise ValueError("포트폴리오 입력에 경기도 28개 시 결과가 모두 있어야 합니다.")
        client = VisitorApiClient(service_key, timeout_seconds=args.timeout, page_size=args.page_size)
        demand_client = TourismDemandApiClient(service_key, timeout_seconds=args.timeout, page_size=args.page_size)
        demand_ym, demand_scores = fetch_latest_common_demand_scores(
            demand_client,
            area_code=config.demand_area_code,
            city_sigungu_codes=ACTIVE_CITY_SIGUNGU_CODES,
            lookback_months=config.demand_lookback_months,
        )
        records = client.fetch_local_daily_visitors(
            start_ymd=f"{demand_ym}01",
            end_ymd=_last_day_of_month(demand_ym),
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError, VisitorApiError, TourismDemandApiError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    results_by_name = {item.definition.region_name: item for item in city_results}
    ranked_regions, matched_names = aggregate_daily_visitor_sums(
        records,
        allowed_region_names=set(results_by_name),
        visitor_type_names=config.visitor_type_names,
    )
    city_scores = build_city_tourism_scores(
        ranked_regions,
        demand_scores,
        city_sigungu_codes=ACTIVE_CITY_SIGUNGU_CODES,
        visitor_weight=config.visitor_weight,
        resource_demand_weight=config.resource_demand_weight,
        demand_intensity_weight=config.demand_intensity_weight,
    )
    selected_scores = city_scores[: config.top_region_count]
    if len(selected_scores) < config.top_region_count:
        print(
            f"오류: 포트폴리오 결과와 이름이 일치하는 방문자 지역이 {len(selected_rows)}개뿐입니다.",
            file=sys.stderr,
        )
        return 2
    selected_results = tuple(results_by_name[item.region_name] for item in selected_scores)
    distributions = build_portfolio_distributions(selected_results)
    generated_at = str(payload.get("generated_at", ""))
    date_stamp = generated_at[:10].replace("-", "") if generated_at else "undated"
    if not re.fullmatch(r"\d{8}", date_stamp):
        date_stamp = "undated"
    stem = f"{config.output_slug}_{date_stamp}"
    output = {
        "benchmark_name": config.benchmark_name,
        "source_portfolio_result": str(input_path),
        "visitor_source_url": config.source_url,
        "visitor_period": {"start_ymd": f"{demand_ym}01", "end_ymd": _last_day_of_month(demand_ym)},
        "visitor_metric": "기간 내 일별 순방문자 수의 합(고유 개인 수 아님)",
        "demand_base_ym": demand_ym,
        "selection_weights": {"visitor": config.visitor_weight, "resource_demand": config.resource_demand_weight, "demand_intensity": config.demand_intensity_weight},
        "selection_scope": "경기도 28개 시(군 제외)",
        "visitor_type_names": list(config.visitor_type_names),
        "observed_visitor_type_names": sorted(
            {record.visitor_type for record in records if record.visitor_type}
        ),
        "api_record_count": len(records),
        "matched_region_count": len(matched_names),
        "city_scores": [item.to_dict() for item in city_scores],
        "selected_regions": [item.to_dict() for item in selected_scores],
        "distributions": [item.to_dict() for item in distributions],
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / f"{stem}.json"
    ranking_path = args.output_dir / f"{stem}_city_tourism_scores.csv"
    distribution_path = args.output_dir / f"{stem}_distributions.csv"
    json_path.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    _write_csv(ranking_path, [item.to_dict() for item in city_scores])
    _write_csv(distribution_path, [item.to_dict() for item in distributions])
    print("완료: 우수 관광 지역 " + ", ".join(item.region_name for item in selected_scores))
    if not config.visitor_type_names:
        print("참고: API 응답의 모든 방문자 구분값을 합산했습니다. JSON의 observed_visitor_type_names를 확인하세요.")
    for path in (json_path, ranking_path, distribution_path):
        print(f"저장: {path}")
    return 0


def fetch_latest_common_demand_scores(
    client: TourismDemandApiClient,
    *,
    area_code: str,
    city_sigungu_codes: dict[str, tuple[str, ...]],
    lookback_months: int,
) -> tuple[str, dict[str, dict[str, TourismDemandRecord]]]:
    expected_codes = {code for codes in city_sigungu_codes.values() for code in codes}
    for base_ym in previous_months(maximum_count=lookback_months):
        scores = client.fetch_all_scores(base_ym=base_ym, area_code=area_code)
        if all(expected_codes.issubset(values) for values in scores.values()):
            return base_ym, scores
    raise TourismDemandApiError("28개 시의 4개 관광 수요 지수가 모두 있는 최근 공통 연월을 찾지 못했습니다.")


def build_city_tourism_scores(
    visitor_rows: list[dict[str, Any]],
    demand_scores: dict[str, dict[str, TourismDemandRecord]],
    *,
    city_sigungu_codes: dict[str, tuple[str, ...]],
    visitor_weight: float,
    resource_demand_weight: float,
    demand_intensity_weight: float,
) -> list[CityTourismScore]:
    visitor_by_name = {str(row["region_name"]): float(row["daily_visitor_sum"]) for row in visitor_rows}
    if set(visitor_by_name) != set(city_sigungu_codes):
        missing = sorted(set(city_sigungu_codes) - set(visitor_by_name))
        raise ValueError("방문자 수가 없는 시: " + ", ".join(missing))
    raw_rows = []
    for city_name, codes in city_sigungu_codes.items():
        values = {key: [demand_scores[key][code].value for code in codes] for key in demand_scores}
        raw_rows.append((
            city_name,
            visitor_by_name[city_name],
            sum(values["resource_service"]) / len(codes) / 2 + sum(values["resource_culture"]) / len(codes) / 2,
            sum(values["intensity_stay"]) / len(codes) / 2 + sum(values["intensity_spend"]) / len(codes) / 2,
        ))
    visitor_percentiles = _percentile_by_name({name: visitor for name, visitor, _, _ in raw_rows})
    resource_percentiles = _percentile_by_name({name: resource for name, _, resource, _ in raw_rows})
    intensity_percentiles = _percentile_by_name({name: intensity for name, _, _, intensity in raw_rows})
    result = [
        CityTourismScore(
            region_name=name,
            visitor_sum=round(visitor, 2), resource_demand=round(resource, 4), demand_intensity=round(intensity, 4),
            visitor_percentile=visitor_percentiles[name], resource_demand_percentile=resource_percentiles[name],
            demand_intensity_percentile=intensity_percentiles[name],
            composite_score=round(visitor_percentiles[name] * visitor_weight + resource_percentiles[name] * resource_demand_weight + intensity_percentiles[name] * demand_intensity_weight, 4),
        )
        for name, visitor, resource, intensity in raw_rows
    ]
    return sorted(result, key=lambda item: (-item.composite_score, item.region_name))


def _percentile_by_name(values: dict[str, float]) -> dict[str, float]:
    ordered = sorted(values.items(), key=lambda item: (item[1], item[0]))
    if len(ordered) == 1:
        return {ordered[0][0]: 100.0}
    result: dict[str, float] = {}
    index = 0
    while index < len(ordered):
        end = index
        while end + 1 < len(ordered) and ordered[end + 1][1] == ordered[index][1]:
            end += 1
        score = round(((index + end) / 2) / (len(ordered) - 1) * 100, 4)
        for position in range(index, end + 1):
            result[ordered[position][0]] = score
        index = end + 1
    return result


def _last_day_of_month(base_ym: str) -> str:
    year, month = int(base_ym[:4]), int(base_ym[4:])
    if month == 12:
        next_year, next_month = year + 1, 1
    else:
        next_year, next_month = year, month + 1
    from datetime import date, timedelta
    return (date(next_year, next_month, 1) - timedelta(days=1)).strftime("%Y%m%d")


def _resolve_input_path(input_path: Path | None, output_dir: Path) -> Path:
    if input_path is not None:
        if not input_path.is_file():
            raise ValueError(f"전체 포트폴리오 결과 파일이 없습니다: {input_path}")
        return input_path
    candidates = sorted(output_dir.glob("gyeonggi_portfolio_benchmark_????????.json"))
    if not candidates:
        raise ValueError("전체 포트폴리오 결과가 없습니다. 먼저 hankkeut-portfolio-benchmark를 실행하세요.")
    return candidates[-1]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = list(rows[0]) if rows else ["region_name"]
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
