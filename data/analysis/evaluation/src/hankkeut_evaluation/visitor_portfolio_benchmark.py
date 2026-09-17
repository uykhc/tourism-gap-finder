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

from hankkeut_calculation.tourism_data.config import resolve_visitor_service_key
from .portfolio_benchmark import (
    build_portfolio_distributions,
    portfolio_region_result_from_dict,
)
from hankkeut_calculation.tourism_data.visitor_api import DailyRegionalVisitor, VisitorApiClient, VisitorApiError
from hankkeut_calculation.tourism_data.tourism_demand_api import (
    TourismDemandApiClient,
    TourismDemandApiError,
    TourismDemandRecord,
    previous_months,
)

DEFAULT_CONFIG_PATH = Path("config/national/performance_evaluator.json")
DEFAULT_OUTPUT_DIR = Path("results/portfolio_benchmarks")

# Backwards-compatible sample scope.  Production callers should pass their own
# nationwide mapping to ``build_regional_tourism_scores`` below.
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
    region_id: str | None = None
    province_name: str | None = None

    def to_dict(self) -> dict[str, Any]:
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
    allowed_region_names: set[str] | None = None,
    allowed_region_ids: set[str] | None = None,
    visitor_type_names: tuple[str, ...] = (),
) -> tuple[list[dict[str, Any]], set[str]]:
    """동일 기간의 일별 방문자 수를 지역별로 더한다.

    이 값은 기간 내 고유 개인 수가 아니라 ``일별 순방문자 수의 합``이다.

    ``allowed_region_ids``를 주면 지역명 대신 ``region_id``(법정동 5자리)로
    걸러 묶는다. 지역명으로 묶으면 중구 5곳, 서구·남구·북구 4곳이 한 덩어리로
    합산되므로 전국 단위에서는 이쪽을 쓴다. 돌려주는 두 번째 값은 실제로
    관측된 키의 집합이며, 묶은 기준에 따라 지역명 또는 region_id다.
    """
    if (allowed_region_names is None) == (allowed_region_ids is None):
        raise ValueError("allowed_region_names 또는 allowed_region_ids 중 하나만 지정해야 합니다.")
    by_region_id = allowed_region_ids is not None
    allowed = allowed_region_ids if by_region_id else allowed_region_names
    selected_types = set(visitor_type_names)
    totals: dict[str, float] = {}
    names_by_key: dict[str, str] = {}
    seen_keys: set[str] = set()
    for record in records:
        key = record.region_id if by_region_id else record.region_name
        if not key or key not in allowed:
            continue
        if selected_types and record.visitor_type not in selected_types:
            continue
        seen_keys.add(key)
        names_by_key.setdefault(key, record.region_name)
        totals[key] = totals.get(key, 0.0) + record.visitor_count
    rows: list[dict[str, Any]] = []
    for key, total in totals.items():
        row: dict[str, Any] = {
            "region_name": names_by_key[key] if by_region_id else key,
            "daily_visitor_sum": round(total, 2),
        }
        if by_region_id:
            row["region_id"] = key
        rows.append(row)
    rows.sort(key=lambda row: (-float(row["daily_visitor_sum"]), str(row["region_name"])))
    for rank, row in enumerate(rows, start=1):
        row["visitor_rank"] = rank
    return rows, seen_keys


def aggregate_daily_visitor_sums_by_region(
    records: list[DailyRegionalVisitor],
    *,
    regions: tuple[Any, ...],
    visitor_type_names: tuple[str, ...] = (),
) -> tuple[list[dict[str, Any]], set[str]]:
    """Aggregate visitor records against nationwide-safe region identifiers.

    The visitor API currently exposes a display name, not an administrative
    code.  A bare name is accepted only when it belongs to one input region;
    names such as ``중구`` are deliberately treated as ambiguous.  Providers
    that return a province-qualified name can be mapped through the automatic
    ``시도명 시군구명`` aliases, or an exact ``visitor_region_name`` configured
    on the portfolio region definition.
    """
    aliases: dict[str, set[str]] = {}
    labels: dict[str, str] = {}
    for item in regions:
        definition = item.definition
        region_id = _region_id(definition.area_code, definition.sigungu_code)
        labels[region_id] = definition.region_name
        names = {
            definition.region_name,
            f"{definition.province_name} {definition.region_name}",
            f"{definition.province_name}{definition.region_name}",
        }
        if definition.visitor_region_name:
            names.add(definition.visitor_region_name)
        for name in names:
            aliases.setdefault(_normalise_region_name(name), set()).add(region_id)

    selected_types = set(visitor_type_names)
    totals: dict[str, float] = {}
    ambiguous_names: set[str] = set()
    for record in records:
        if selected_types and record.visitor_type not in selected_types:
            continue
        candidates = aliases.get(_normalise_region_name(record.region_name), set())
        if len(candidates) == 1:
            region_id = next(iter(candidates))
            totals[region_id] = totals.get(region_id, 0.0) + record.visitor_count
        elif len(candidates) > 1:
            ambiguous_names.add(record.region_name)
    if ambiguous_names:
        raise ValueError(
            "전국 방문자 API의 동명 지역을 코드 없이 구분할 수 없습니다: "
            + ", ".join(sorted(ambiguous_names))
            + ". 원천 응답의 시도 표기를 사용하거나 visitor_region_name을 설정하세요."
        )
    rows = [
        {
            "region_id": region_id,
            "region_name": labels[region_id],
            "daily_visitor_sum": round(total, 2),
        }
        for region_id, total in totals.items()
    ]
    rows.sort(key=lambda row: (-float(row["daily_visitor_sum"]), str(row["region_id"])))
    for rank, row in enumerate(rows, start=1):
        row["visitor_rank"] = rank
    return rows, set(totals)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="전국 시군구의 방문자·관광 수요 지수로 우수 관광 지역을 선정합니다."
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
        if not all_results:
            raise ValueError("포트폴리오 입력에 성공한 지역 결과가 없습니다.")
        client = VisitorApiClient(service_key, timeout_seconds=args.timeout, page_size=args.page_size)
        demand_client = TourismDemandApiClient(service_key, timeout_seconds=args.timeout, page_size=args.page_size)
        demand_ym, demand_scores = fetch_latest_common_demand_scores_by_area(
            demand_client,
            regions=all_results,
            lookback_months=config.demand_lookback_months,
        )
        records = client.fetch_local_daily_visitors(
            start_ymd=f"{demand_ym}01",
            end_ymd=_last_day_of_month(demand_ym),
        )
    except (OSError, json.JSONDecodeError, KeyError, ValueError, VisitorApiError, TourismDemandApiError) as exc:
        print(f"오류: {exc}", file=sys.stderr)
        return 2

    results_by_id = {
        _region_id(item.definition.area_code, item.definition.sigungu_code): item
        for item in all_results
    }
    if len(results_by_id) != len(all_results):
        raise ValueError("포트폴리오 입력에 중복된 시도·시군구 코드가 있습니다.")
    ranked_regions, matched_region_ids = aggregate_daily_visitor_sums_by_region(
        records,
        regions=all_results,
        visitor_type_names=config.visitor_type_names,
    )
    region_codes = {
        _region_id(item.definition.area_code, item.definition.sigungu_code): (
            _region_id(item.definition.area_code, item.definition.sigungu_code),
        )
        for item in all_results
    }
    region_labels = {
        _region_id(item.definition.area_code, item.definition.sigungu_code): item.definition.region_name
        for item in all_results
    }
    province_names = {
        _region_id(item.definition.area_code, item.definition.sigungu_code): item.definition.province_name
        for item in all_results
    }
    city_scores = build_regional_tourism_scores(
        ranked_regions,
        demand_scores,
        region_sigungu_codes=region_codes,
        visitor_weight=config.visitor_weight,
        resource_demand_weight=config.resource_demand_weight,
        demand_intensity_weight=config.demand_intensity_weight,
        region_labels=region_labels,
        province_names=province_names,
    )
    selected_scores = city_scores[: config.top_region_count]
    if len(selected_scores) < config.top_region_count:
        print(f"오류: 선정 가능한 지역이 {len(selected_scores)}개뿐입니다.", file=sys.stderr)
        return 2
    selected_results = tuple(results_by_id[item.region_id] for item in selected_scores if item.region_id)
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
        "selection_scope": "입력 포트폴리오에 포함된 전국 시군구(시도·시군구 코드 기준)",
        "visitor_type_names": list(config.visitor_type_names),
        "observed_visitor_type_names": sorted(
            {record.visitor_type for record in records if record.visitor_type}
        ),
        "api_record_count": len(records),
        "matched_region_count": len(matched_region_ids),
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
    print("완료: 우수 관광 지역 " + ", ".join(
        f"{item.province_name} {item.region_name}" if item.province_name else item.region_name
        for item in selected_scores
    ))
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


def fetch_latest_common_demand_scores_by_area(
    client: TourismDemandApiClient,
    *,
    regions: tuple[Any, ...],
    lookback_months: int,
) -> tuple[str, dict[str, dict[str, TourismDemandRecord]]]:
    """Fetch a single common month for every province represented in input.

    The tourism-demand API's signgu code is only unique inside ``area_code``;
    returned dictionaries therefore use ``<area_code>:<sigungu_code>`` keys.
    """
    expected = {(item.definition.area_code, item.definition.sigungu_code) for item in regions}
    area_codes = sorted({area for area, _ in expected})
    for base_ym in previous_months(maximum_count=lookback_months):
        per_area = {area: client.fetch_all_scores(base_ym=base_ym, area_code=area) for area in area_codes}
        if all(
            all(sigungu in values for values in per_area[area].values())
            for area, sigungu in expected
        ):
            return base_ym, {
                metric: {
                    f"{area}:{sigungu}": values[metric][sigungu]
                    for area, sigungu in expected
                    for values in (per_area[area],)
                }
                for metric in ("resource_service", "resource_culture", "intensity_stay", "intensity_spend")
            }
    raise TourismDemandApiError("입력 전국 시군구의 4개 관광 수요 지수가 모두 있는 최근 공통 연월을 찾지 못했습니다.")


def build_city_tourism_scores(
    visitor_rows: list[dict[str, Any]],
    demand_scores: dict[str, dict[str, TourismDemandRecord]],
    *,
    city_sigungu_codes: dict[str, tuple[str, ...]],
    visitor_weight: float,
    resource_demand_weight: float,
    demand_intensity_weight: float,
) -> list[CityTourismScore]:
    """Deprecated compatibility wrapper for the former Gyeonggi-only CLI."""
    return build_regional_tourism_scores(
        visitor_rows,
        demand_scores,
        region_sigungu_codes=city_sigungu_codes,
        visitor_weight=visitor_weight,
        resource_demand_weight=resource_demand_weight,
        demand_intensity_weight=demand_intensity_weight,
    )


def build_regional_tourism_scores(
    visitor_rows: list[dict[str, Any]],
    demand_scores: dict[str, dict[str, TourismDemandRecord]],
    *,
    region_sigungu_codes: dict[str, tuple[str, ...]],
    visitor_weight: float,
    resource_demand_weight: float,
    demand_intensity_weight: float,
    region_labels: dict[str, str] | None = None,
    province_names: dict[str, str] | None = None,
) -> list[CityTourismScore]:
    """Rank any configured set of regions, rather than a fixed province.

    ``region_sigungu_codes`` is deliberately supplied by the caller.  The
    demand API uses province-local signgu codes, while API consumers use a
    nationwide five-digit region id; keeping that mapping in configuration
    prevents silent name-based joins (``중구`` etc.) across provinces.
    """
    # 조인 키는 행이 region_id를 들고 있으면 그것, 없으면 지역명이다. 이 함수는
    # 키가 무엇인지 알 필요가 없다. region_sigungu_codes를 호출측이 주는 이유가
    # 바로 지역명 조인을 피하기 위한 것이다.
    visitor_by_key = {
        str(row.get("region_id") or row["region_name"]): float(row["daily_visitor_sum"])
        for row in visitor_rows
    }
    names_by_key = {
        str(row.get("region_id") or row["region_name"]): str(row["region_name"])
        for row in visitor_rows
    }
    ids_by_key = {
        str(row["region_id"]): str(row["region_id"])
        for row in visitor_rows
        if row.get("region_id")
    }
    if set(visitor_by_key) != set(region_sigungu_codes):
        missing = sorted(set(region_sigungu_codes) - set(visitor_by_key))
        raise ValueError("방문자 수가 없는 지역: " + ", ".join(missing))
    raw_rows = []
    for region_id, codes in region_sigungu_codes.items():
        values = {key: [demand_scores[key][code].value for code in codes] for key in demand_scores}
        raw_rows.append((
            region_id,
            visitor_by_key[region_id],
            sum(values["resource_service"]) / len(codes) / 2 + sum(values["resource_culture"]) / len(codes) / 2,
            sum(values["intensity_stay"]) / len(codes) / 2 + sum(values["intensity_spend"]) / len(codes) / 2,
        ))
    visitor_percentiles = _percentile_by_name({name: visitor for name, visitor, _, _ in raw_rows})
    resource_percentiles = _percentile_by_name({name: resource for name, _, resource, _ in raw_rows})
    intensity_percentiles = _percentile_by_name({name: intensity for name, _, _, intensity in raw_rows})
    result = [
        CityTourismScore(
            region_name=(region_labels or {}).get(name, names_by_key.get(name, name)),
            visitor_sum=round(visitor, 2), resource_demand=round(resource, 4), demand_intensity=round(intensity, 4),
            visitor_percentile=visitor_percentiles[name], resource_demand_percentile=resource_percentiles[name],
            demand_intensity_percentile=intensity_percentiles[name],
            composite_score=round(visitor_percentiles[name] * visitor_weight + resource_percentiles[name] * resource_demand_weight + intensity_percentiles[name] * demand_intensity_weight, 4),
            region_id=ids_by_key.get(name, name if region_labels is not None else ""),
            province_name=(province_names or {}).get(name),
        )
        for name, visitor, resource, intensity in raw_rows
    ]
    return sorted(result, key=lambda item: (-item.composite_score, item.region_name, item.region_id or ""))


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


def _region_id(area_code: str, sigungu_code: str) -> str:
    return f"{area_code}:{sigungu_code}"


def _normalise_region_name(value: str) -> str:
    return re.sub(r"\s+", "", value).strip()


def _resolve_input_path(input_path: Path | None, output_dir: Path) -> Path:
    if input_path is not None:
        if not input_path.is_file():
            raise ValueError(f"전체 포트폴리오 결과 파일이 없습니다: {input_path}")
        return input_path
    candidates = sorted(output_dir.glob("*_portfolio_benchmark_????????.json"))
    if not candidates:
        raise ValueError("전체 포트폴리오 결과가 없습니다. 먼저 hankkeut-portfolio-benchmark를 실행하세요.")
    return candidates[-1]


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fieldnames = list(rows[0]) if rows else ["region_name"]
    with path.open("w", encoding="utf-8-sig", newline="") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
