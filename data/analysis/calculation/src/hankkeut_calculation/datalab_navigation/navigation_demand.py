"""Validate Data Lab navigation CSV exports and calculate target supply pressure."""

from __future__ import annotations

import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from ..kakao_places.content_store import psycopg_connection_url

DEFAULT_TAXONOMY_PATH = Path("config/datalab/navigation_destination_type_taxonomy.json")
MONTHLY_REQUIRED_COLUMNS = ("기준연월", "목적지 유형", "목적지 검색량")
AGGREGATE_REQUIRED_COLUMNS = ("카테고리중분류명", "유형별 검색건수")


@dataclass(frozen=True, slots=True)
class SourceTypeRule:
    content_type: str | None
    include: bool


@dataclass(frozen=True, slots=True)
class NavigationDemandTaxonomy:
    version: str
    content_types: tuple[str, ...]
    source_type_rules: dict[str, SourceTypeRule]
    total_source_type: str


@dataclass(frozen=True, slots=True)
class NavigationDemandRecord:
    base_ym: str
    source_type: str
    search_count: int
    content_type: str | None
    included: bool
    source_value_inferred: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_ym": self.base_ym,
            "source_type": self.source_type,
            "search_count": self.search_count,
            "content_type": self.content_type,
            "included": self.included,
            "source_value_inferred": self.source_value_inferred,
        }


@dataclass(frozen=True, slots=True)
class NavigationDemandImport:
    region_name: str
    source_file: str
    taxonomy_version: str
    records: tuple[NavigationDemandRecord, ...]
    input_granularity: str = "monthly"
    period_start_ym: str | None = None
    period_end_ym: str | None = None
    period_month_count: int | None = None

    @property
    def available_months(self) -> tuple[str, ...]:
        return tuple(sorted({record.base_ym for record in self.records}))

    def select_latest_months(self, month_count: int) -> tuple[NavigationDemandRecord, ...]:
        if month_count < 1:
            raise ValueError("month_count는 1 이상이어야 합니다.")
        if self.input_granularity == "period_total":
            if month_count != self.period_month_count:
                raise ValueError(
                    f"기간 합계 파일은 {self.period_month_count}개월 기준입니다: "
                    f"requested={month_count}"
                )
            return self.records
        months = self.available_months
        if len(months) < month_count:
            raise ValueError(f"요청한 {month_count}개월보다 CSV의 월 수({len(months)})가 적습니다.")
        selected_months = set(months[-month_count:])
        return tuple(record for record in self.records if record.base_ym in selected_months)

    def to_dict(self) -> dict[str, Any]:
        return {
            "region_name": self.region_name,
            "source_file": self.source_file,
            "taxonomy_version": self.taxonomy_version,
            "input_granularity": self.input_granularity,
            "analysis_period": {
                "start_ym": self.period_start_ym,
                "end_ym": self.period_end_ym,
                "month_count": self.period_month_count,
            },
            "available_months": list(self.available_months),
            "records": [record.to_dict() for record in self.records],
        }


def load_navigation_demand_taxonomy(path: Path = DEFAULT_TAXONOMY_PATH) -> NavigationDemandTaxonomy:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"Navigation-demand taxonomy file does not exist: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"Navigation-demand taxonomy is not valid JSON: {path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("Navigation-demand taxonomy must be an object.")
    version = _required_string(payload, "version")
    content_types = _string_tuple(payload.get("content_types"), "content_types")
    raw_rules = payload.get("source_type_rules")
    if not isinstance(raw_rules, dict):
        raise ValueError("source_type_rules must be an object.")
    rules: dict[str, SourceTypeRule] = {}
    for raw_source_type, raw_rule in raw_rules.items():
        source_type = str(raw_source_type).strip()
        if not source_type or not isinstance(raw_rule, dict) or not isinstance(raw_rule.get("include"), bool):
            raise ValueError("Every source_type_rules entry needs a source type and boolean include.")
        content_type = raw_rule.get("content_type")
        if content_type is not None:
            content_type = str(content_type).strip()
        if raw_rule["include"] and content_type not in content_types:
            raise ValueError("Included source types must map to a declared content type.")
        if not raw_rule["include"] and content_type is not None:
            raise ValueError("Excluded source types must use null content_type.")
        rules[source_type] = SourceTypeRule(content_type, raw_rule["include"])
    total_source_type = _required_string(payload, "total_source_type")
    return NavigationDemandTaxonomy(version, content_types, rules, total_source_type)


def import_navigation_demand_csv(
    path: Path,
    *,
    region_name: str,
    taxonomy: NavigationDemandTaxonomy,
    period_start_ym: str | None = None,
    period_end_ym: str | None = None,
) -> NavigationDemandImport:
    if not region_name.strip():
        raise ValueError("region_name은 비어 있을 수 없습니다.")
    try:
        csv_file = path.open(encoding="utf-8-sig", newline="")
    except FileNotFoundError as exc:
        raise ValueError(f"Navigation-demand CSV file does not exist: {path}") from exc
    with csv_file:
        reader = csv.DictReader(csv_file)
        columns = tuple(str(name or "").strip() for name in (reader.fieldnames or ()))
        if columns == MONTHLY_REQUIRED_COLUMNS:
            return _import_monthly_rows(
                reader, path=path, region_name=region_name, taxonomy=taxonomy
            )
        if set(AGGREGATE_REQUIRED_COLUMNS).issubset(columns):
            return _import_aggregate_rows(
                reader,
                path=path,
                region_name=region_name,
                taxonomy=taxonomy,
                period_start_ym=period_start_ym,
                period_end_ym=period_end_ym,
            )
        raise ValueError(
            "CSV 헤더는 월별 형식(기준연월, 목적지 유형, 목적지 검색량) 또는 "
            "기간 합계 형식(카테고리중분류명, 유형별 검색건수)이어야 합니다."
        )


def _import_monthly_rows(
    reader: csv.DictReader,
    *,
    path: Path,
    region_name: str,
    taxonomy: NavigationDemandTaxonomy,
) -> NavigationDemandImport:
    records: list[NavigationDemandRecord] = []
    seen: set[tuple[str, str]] = set()
    for row_number, row in enumerate(reader, start=2):
        base_ym = str(row.get("기준연월", "")).strip()
        source_type = str(row.get("목적지 유형", "")).strip()
        search_count = _parse_non_negative_int(row.get("목적지 검색량"), row_number)
        if len(base_ym) != 6 or not base_ym.isdigit() or not 1 <= int(base_ym[4:]) <= 12:
            raise ValueError(f"{row_number}행 기준연월은 YYYYMM 형식이어야 합니다.")
        if not source_type:
            raise ValueError(f"{row_number}행 목적지 유형이 비어 있습니다.")
        key = (base_ym, source_type)
        if key in seen:
            raise ValueError(f"중복된 기준연월/목적지 유형 행이 있습니다: {base_ym}/{source_type}")
        seen.add(key)
        rule = None if source_type == taxonomy.total_source_type else taxonomy.source_type_rules.get(source_type)
        if rule is None and source_type != taxonomy.total_source_type:
            raise ValueError(f"{row_number}행 목적지 유형이 taxonomy에 없습니다: {source_type}")
        records.append(NavigationDemandRecord(
            base_ym=base_ym,
            source_type=source_type,
            search_count=search_count,
            content_type=None if rule is None else rule.content_type,
            included=False if rule is None else rule.include,
        ))
    if not records:
        raise ValueError("CSV에 데이터 행이 없습니다.")
    _fill_omitted_zero_source_types(records, taxonomy)
    _validate_monthly_totals(records, taxonomy)
    months = sorted({record.base_ym for record in records})
    return NavigationDemandImport(
        region_name.strip(),
        str(path),
        taxonomy.version,
        tuple(records),
        input_granularity="monthly",
        period_start_ym=months[0],
        period_end_ym=months[-1],
        period_month_count=len(months),
    )


def _import_aggregate_rows(
    reader: csv.DictReader,
    *,
    path: Path,
    region_name: str,
    taxonomy: NavigationDemandTaxonomy,
    period_start_ym: str | None,
    period_end_ym: str | None,
) -> NavigationDemandImport:
    if not period_start_ym or not period_end_ym:
        raise ValueError("기간 합계 CSV에는 period_start_ym과 period_end_ym이 필요합니다.")
    period_months = _month_range(period_start_ym, period_end_ym)
    records: list[NavigationDemandRecord] = []
    seen: set[str] = set()
    for row_number, row in enumerate(reader, start=2):
        source_type = str(row.get("카테고리중분류명") or "").strip()
        if not source_type:
            continue
        if source_type in seen:
            raise ValueError(f"중복된 카테고리중분류명이 있습니다: {source_type}")
        rule = taxonomy.source_type_rules.get(source_type)
        if rule is None:
            raise ValueError(f"{row_number}행 카테고리중분류명이 taxonomy에 없습니다: {source_type}")
        seen.add(source_type)
        records.append(NavigationDemandRecord(
            base_ym=period_end_ym,
            source_type=source_type,
            search_count=_parse_non_negative_int(row.get("유형별 검색건수"), row_number),
            content_type=rule.content_type,
            included=rule.include,
        ))
    missing = set(taxonomy.source_type_rules) - seen
    if missing:
        raise ValueError("기간 합계 CSV에 필요한 관광 유형이 없습니다: " + ", ".join(sorted(missing)))
    if not records:
        raise ValueError("CSV에 데이터 행이 없습니다.")
    records.append(NavigationDemandRecord(
        base_ym=period_end_ym,
        source_type=taxonomy.total_source_type,
        search_count=sum(record.search_count for record in records),
        content_type=None,
        included=False,
        source_value_inferred=True,
    ))
    return NavigationDemandImport(
        region_name.strip(),
        str(path),
        taxonomy.version,
        tuple(records),
        input_granularity="period_total",
        period_start_ym=period_start_ym,
        period_end_ym=period_end_ym,
        period_month_count=len(period_months),
    )


def _month_range(start_ym: str, end_ym: str) -> tuple[str, ...]:
    for value, label in ((start_ym, "period_start_ym"), (end_ym, "period_end_ym")):
        if len(value) != 6 or not value.isdigit() or not 1 <= int(value[4:]) <= 12:
            raise ValueError(f"{label}은 YYYYMM 형식이어야 합니다.")
    start_index = int(start_ym[:4]) * 12 + int(start_ym[4:]) - 1
    end_index = int(end_ym[:4]) * 12 + int(end_ym[4:]) - 1
    if end_index < start_index:
        raise ValueError("period_end_ym은 period_start_ym보다 빠를 수 없습니다.")
    return tuple(
        f"{index // 12:04d}{index % 12 + 1:02d}"
        for index in range(start_index, end_index + 1)
    )


def build_supply_pressure_report(
    demand_import: NavigationDemandImport,
    *,
    taxonomy: NavigationDemandTaxonomy,
    content_database_url: str,
    region_id: str,
    month_count: int = 12,
) -> dict[str, Any]:
    selected_records = demand_import.select_latest_months(month_count)
    supply_region = _load_kakao_supply_from_database(
        content_database_url, region_id, taxonomy.content_types,
    )
    demand_by_type = _aggregate_by_content_type(selected_records, included=True)
    excluded_by_type = _aggregate_by_content_type(selected_records, included=False)
    total_by_month = _aggregate_total_by_month(selected_records, taxonomy.total_source_type)
    included_total = sum(demand_by_type.values())
    excluded_total = sum(excluded_by_type.values())
    metrics = []
    for content_type in taxonomy.content_types:
        supply_count = supply_region["content_type_counts"][content_type]
        if supply_count < 1:
            raise ValueError(f"카카오 공급 장소 수가 0입니다: {content_type}")
        search_count = demand_by_type.get(content_type, 0)
        metrics.append({
            "content_type": content_type,
            "navigation_search_count": search_count,
            "kakao_supply_place_count": supply_count,
            "searches_per_place": round(search_count / supply_count, 4),
        })
    metrics.sort(key=lambda item: (-item["searches_per_place"], item["content_type"]))
    selected_months = sorted({record.base_ym for record in selected_records})
    if demand_import.input_granularity == "period_total":
        start_ym = str(demand_import.period_start_ym)
        end_ym = str(demand_import.period_end_ym)
        selection = "fixed_period_total"
        available_start_ym = start_ym
        available_end_ym = end_ym
    else:
        start_ym = selected_months[0]
        end_ym = selected_months[-1]
        selection = "latest_available_months"
        available_start_ym = demand_import.available_months[0]
        available_end_ym = demand_import.available_months[-1]
    warnings = []
    if not supply_region["is_complete"]:
        warnings.append("카카오 장소 수집에 잘린 타일이 있어 공급압력은 잠정값입니다.")
    if excluded_total:
        warnings.append("기타관광은 분석에서 제외했으며 원본 검색량 합계에는 포함됩니다.")
    return {
        "report_version": "2026-09-05",
        "region_name": demand_import.region_name,
        "analysis_period": {
            "selection": selection,
            "month_count": month_count,
            "start_ym": start_ym,
            "end_ym": end_ym,
            "available_source_start_ym": available_start_ym,
            "available_source_end_ym": available_end_ym,
        },
        "provenance": {
            "demand_source": "한국관광 데이터랩",
            "demand_source_file": demand_import.source_file,
            "demand_input_granularity": demand_import.input_granularity,
            "demand_taxonomy_version": taxonomy.version,
            "kakao_supply_source": supply_region["source"],
            "kakao_taxonomy_version": supply_region["taxonomy_version"],
        },
        "data_quality": {
            "kakao_supply_is_complete": supply_region["is_complete"],
            "kakao_truncated_tile_count": supply_region["truncated_tile_count"],
            "warnings": warnings,
        },
        "demand_summary": {
            "all_source_type_search_count": sum(total_by_month.values()),
            "included_six_type_search_count": included_total,
            "excluded_source_type_search_count": excluded_total,
            "excluded_source_type_counts": dict(sorted(excluded_by_type.items())),
        },
        "content_type_metrics": metrics,
        "ai_report_context": {
            "region_name": demand_import.region_name,
            "analysis_period": f"{start_ym}~{end_ym}",
            "metric_definition": "유형별 내비게이션 목적지 검색량 ÷ 카카오맵 유형별 장소 수",
            "limitation": "단일 지역 결과이므로 전국 또는 Peer percentile은 산출하지 않았습니다.",
            "priority_order_by_supply_pressure": [metric["content_type"] for metric in metrics],
            "content_type_metrics": metrics,
            "evidence": [
                {
                    "content_type": metric["content_type"],
                    "navigation_search_count": metric["navigation_search_count"],
                    "kakao_supply_place_count": metric["kakao_supply_place_count"],
                    "searches_per_place": metric["searches_per_place"],
                }
                for metric in metrics
            ],
        },
    }


def _validate_monthly_totals(records: list[NavigationDemandRecord], taxonomy: NavigationDemandTaxonomy) -> None:
    by_month: dict[str, list[NavigationDemandRecord]] = defaultdict(list)
    for record in records:
        by_month[record.base_ym].append(record)
    for base_ym, month_records in by_month.items():
        source_types = {record.source_type for record in month_records}
        expected_types = {taxonomy.total_source_type, *taxonomy.source_type_rules}
        unexpected_types = source_types - expected_types
        if unexpected_types:
            raise ValueError(
                f"{base_ym}의 목적지 유형 구성이 올바르지 않습니다: "
                f"unexpected={sorted(unexpected_types)}"
            )
        totals = [record.search_count for record in month_records if record.source_type == taxonomy.total_source_type]
        if len(totals) != 1:
            raise ValueError(f"{base_ym}의 전체 행이 정확히 하나여야 합니다.")
        category_sum = sum(record.search_count for record in month_records if record.source_type != taxonomy.total_source_type)
        if totals[0] != category_sum:
            raise ValueError(f"{base_ym}의 전체 검색량({totals[0]})과 유형별 합계({category_sum})가 다릅니다.")


def _fill_omitted_zero_source_types(records: list[NavigationDemandRecord], taxonomy: NavigationDemandTaxonomy) -> None:
    """Restore a source-type row only when the CSV's total proves it is zero.

    Data Lab occasionally omits a type whose monthly count is zero.  A missing
    non-zero value must never be guessed, so restoration is allowed only when
    the published total exactly equals the sum of the rows that are present.
    """
    by_month: dict[str, list[NavigationDemandRecord]] = defaultdict(list)
    for record in records:
        by_month[record.base_ym].append(record)
    restored: list[NavigationDemandRecord] = []
    expected_categories = set(taxonomy.source_type_rules)
    for base_ym, month_records in by_month.items():
        source_types = {record.source_type for record in month_records}
        missing_categories = expected_categories - source_types
        if not missing_categories:
            continue
        totals = [record.search_count for record in month_records if record.source_type == taxonomy.total_source_type]
        present_category_sum = sum(record.search_count for record in month_records if record.source_type != taxonomy.total_source_type)
        if len(totals) != 1 or totals[0] != present_category_sum:
            raise ValueError(
                f"{base_ym}의 누락 목적지 유형은 0으로 보완할 수 없습니다: "
                f"missing={sorted(missing_categories)}"
            )
        for source_type in sorted(missing_categories):
            rule = taxonomy.source_type_rules[source_type]
            restored.append(NavigationDemandRecord(
                base_ym=base_ym,
                source_type=source_type,
                search_count=0,
                content_type=rule.content_type,
                included=rule.include,
                source_value_inferred=True,
            ))
    records.extend(restored)


def _aggregate_by_content_type(records: tuple[NavigationDemandRecord, ...], *, included: bool) -> dict[str, int]:
    values: dict[str, int] = defaultdict(int)
    for record in records:
        if record.included == included and record.content_type is not None:
            values[record.content_type] += record.search_count
        elif not included and not record.included and record.source_type != "전체":
            values[record.source_type] += record.search_count
    return dict(values)


def _aggregate_total_by_month(records: tuple[NavigationDemandRecord, ...], total_source_type: str) -> dict[str, int]:
    return {record.base_ym: record.search_count for record in records if record.source_type == total_source_type}


def _load_kakao_supply_from_database(
    database_url: str,
    region_id: str,
    content_types: tuple[str, ...],
) -> dict[str, Any]:
    """Read the newest completed content-collection run for one region."""
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - depends on optional extra
        raise ValueError("Postgres 조회에는 psycopg가 필요합니다. database extra를 설치하세요.") from exc
    query = """
        with latest_run as (
          select r.run_id, r.taxonomy_version, r.collected_at
          from public.content_collection_runs r
          join public.region_content_counts c on c.run_id = r.run_id
          where r.status = 'completed' and c.region_id = %s
          order by r.collected_at desc
          limit 1
        )
        select c.content_type, c.place_count, c.is_complete,
               c.truncated_tile_count, latest_run.taxonomy_version,
               latest_run.collected_at
        from public.region_content_counts c
        join latest_run on latest_run.run_id = c.run_id
        where c.region_id = %s
    """
    try:
        with psycopg.connect(psycopg_connection_url(database_url)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (region_id, region_id))
                rows = cursor.fetchall()
    except psycopg.Error as exc:
        raise ValueError(f"카카오 공급 DB 조회에 실패했습니다: {exc}") from exc
    if not rows:
        raise ValueError(f"완료된 카카오 콘텐츠 수집 결과가 없습니다: {region_id}")
    counts: dict[str, int] = {}
    complete_values: list[bool] = []
    truncated_count = 0
    taxonomy_versions: set[str] = set()
    collected_values: set[str] = set()
    for content_type, place_count, is_complete, truncated, taxonomy_version, collected_at in rows:
        if content_type in counts:
            raise ValueError(f"카카오 공급 DB에 중복 유형이 있습니다: {content_type}")
        counts[str(content_type)] = int(place_count)
        complete_values.append(bool(is_complete))
        # The collector currently records its region-wide truncation count on
        # every one of the six aggregate rows.  Use max rather than sum so the
        # report does not multiply the same quality warning six times.
        truncated_count = max(truncated_count, int(truncated))
        taxonomy_versions.add(str(taxonomy_version))
        collected_values.add(str(collected_at))
    missing = [content_type for content_type in content_types if content_type not in counts]
    if missing:
        raise ValueError("카카오 공급 DB에 콘텐츠 유형이 없습니다: " + ", ".join(missing))
    if len(taxonomy_versions) != 1 or len(collected_values) != 1:
        raise ValueError("카카오 공급 DB의 최신 수집 실행 메타데이터가 일관되지 않습니다.")
    return {
        "content_type_counts": {content_type: counts[content_type] for content_type in content_types},
        "taxonomy_version": next(iter(taxonomy_versions)),
        "truncated_tile_count": truncated_count,
        "is_complete": all(complete_values),
        "source": f"postgres:region_content_counts/{region_id}",
    }


def _parse_non_negative_int(value: Any, row_number: int) -> int:
    try:
        parsed = int(str(value).replace(",", "").strip())
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{row_number}행 목적지 검색량이 정수가 아닙니다.") from exc
    if parsed < 0:
        raise ValueError(f"{row_number}행 목적지 검색량은 음수일 수 없습니다.")
    return parsed


def _required_string(payload: dict[str, Any], field: str) -> str:
    value = str(payload.get(field, "")).strip()
    if not value:
        raise ValueError(f"{field}은 비어 있을 수 없습니다.")
    return value


def _string_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value or not all(isinstance(item, str) and item.strip() for item in value):
        raise ValueError(f"{field} must be a non-empty string array.")
    return tuple(item.strip() for item in value)
