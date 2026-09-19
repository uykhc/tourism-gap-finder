"""Read one immutable Kakao supply collection run through a narrow provider."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Protocol, Sequence

from ..kakao_places.content_store import psycopg_connection_url

CONTENT_TYPES = (
    "FOOD", "ACCOMMODATION", "CULTURE_TOURISM",
    "EXPERIENCE_TOURISM", "LEISURE_SPORTS", "SHOPPING",
)

CONTENT_TYPE_ALIASES = {
    "FOOD": "FOOD", "음식": "FOOD",
    "ACCOMMODATION": "ACCOMMODATION", "숙박": "ACCOMMODATION",
    "CULTURE_TOURISM": "CULTURE_TOURISM", "문화관광": "CULTURE_TOURISM",
    "EXPERIENCE_TOURISM": "EXPERIENCE_TOURISM", "체험관광": "EXPERIENCE_TOURISM",
    "LEISURE_SPORTS": "LEISURE_SPORTS", "레저스포츠": "LEISURE_SPORTS",
    "SHOPPING": "SHOPPING", "쇼핑": "SHOPPING",
}


class SupplyProvider(Protocol):
    def get_region(
        self, region_id: str, content_types: Sequence[str] = CONTENT_TYPES
    ) -> dict[str, Any]: ...


@dataclass(frozen=True, slots=True)
class KakaoSupplyRun:
    run_id: str
    taxonomy_version: str
    collected_at: str
    regions: dict[str, dict[str, Any]]
    normalized_sha256: str


class PostgresKakaoSupplyProvider:
    """Validated adapter using the latest complete collection for each region."""

    def __init__(
        self,
        database_url: str,
        *,
        required_region_ids: Sequence[str] = (),
        require_complete: bool = True,
    ) -> None:
        if not database_url.strip():
            raise ValueError("CONTENT_DATABASE_URL이 필요합니다.")
        if not required_region_ids:
            raise ValueError("required_region_ids is required for Kakao DB queries")
        self.run = _read_latest_complete_regions(
            database_url,
            required_region_ids=required_region_ids,
            require_complete=require_complete,
        )

    def get_region(
        self, region_id: str, content_types: Sequence[str] = CONTENT_TYPES
    ) -> dict[str, Any]:
        expected = tuple(content_types)
        if set(expected) != set(CONTENT_TYPES) or len(expected) != len(CONTENT_TYPES):
            raise ValueError("Kakao 공급 유형은 영문 표준 6개 코드여야 합니다.")
        try:
            row = self.run.regions[region_id]
        except KeyError as exc:
            raise ValueError(f"Kakao DB run에 지역이 없습니다: {region_id}") from exc
        counts = row["content_type_counts"]
        return {
            "content_type_counts": {name: counts[name] for name in expected},
            "taxonomy_version": row["taxonomy_version"],
            "truncated_tile_count": row["truncated_tile_count"],
            "is_complete": row["is_complete"],
            "source": f"postgres:region_content_counts/{row['run_id']}/{region_id}",
        }


class MemorySupplyProvider:
    """In-memory provider for deterministic tests; never a release fallback."""

    def __init__(
        self,
        regions: Mapping[str, Mapping[str, Any]],
        *,
        taxonomy_version: str = "test",
        collection_id: str = "memory-test",
    ) -> None:
        self._regions = {key: dict(value) for key, value in regions.items()}
        self._taxonomy_version = taxonomy_version
        self._collection_id = collection_id

    def get_region(
        self, region_id: str, content_types: Sequence[str] = CONTENT_TYPES
    ) -> dict[str, Any]:
        try:
            row = self._regions[region_id]
        except KeyError as exc:
            raise ValueError(f"테스트 공급 데이터에 지역이 없습니다: {region_id}") from exc
        counts = row.get("content_type_counts")
        if not isinstance(counts, Mapping):
            raise ValueError(f"테스트 공급 데이터의 유형별 건수가 없습니다: {region_id}")
        return {
            "content_type_counts": {name: counts[name] for name in content_types},
            "taxonomy_version": self._taxonomy_version,
            "truncated_tile_count": int(row.get("truncated_tile_count", 0)),
            "is_complete": bool(row.get("is_complete", True)),
            "source": f"memory-test:{self._collection_id}/{region_id}",
        }


def normalize_supply_run(
    metadata: Mapping[str, Any],
    rows: Sequence[Sequence[Any]],
    *,
    required_region_ids: Sequence[str] = (),
    require_complete: bool = True,
    require_completed: bool = True,
) -> KakaoSupplyRun:
    run_id = _required_string(metadata, "run_id")
    taxonomy_version = _required_string(metadata, "taxonomy_version")
    collected_at = _required_string(metadata, "collected_at")
    if require_completed and metadata.get("status") != "completed":
        raise ValueError(f"Kakao 수집 run이 completed 상태가 아닙니다: {run_id}")
    try:
        datetime.fromisoformat(collected_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("Kakao run collected_at은 ISO-8601 형식이어야 합니다.") from exc

    required = set(required_region_ids)
    regions: dict[str, dict[str, Any]] = {}
    for row in rows:
        if len(row) != 5:
            raise ValueError("Kakao 공급 DB 조회 행 형식이 올바르지 않습니다.")
        raw_region_id, raw_type, count, is_complete, truncated = row
        region_id = str(raw_region_id).strip()
        if len(region_id) != 5 or not region_id.isdigit():
            raise ValueError(f"Kakao DB region_id는 5자리 숫자여야 합니다: {region_id}")
        if required and region_id not in required:
            continue
        content_type = CONTENT_TYPE_ALIASES.get(str(raw_type).strip())
        if content_type is None:
            raise ValueError(f"Kakao DB 콘텐츠 유형을 알 수 없습니다: {raw_type}")
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(
                f"Kakao DB 장소 수는 0 이상의 정수여야 합니다: {region_id}/{raw_type}"
            )
        if not isinstance(is_complete, bool):
            raise ValueError(f"Kakao DB is_complete는 boolean이어야 합니다: {region_id}")
        if isinstance(truncated, bool) or not isinstance(truncated, int) or truncated < 0:
            raise ValueError(
                f"Kakao DB truncated_tile_count는 0 이상의 정수여야 합니다: {region_id}"
            )
        region = regions.setdefault(region_id, {
            "region_id": region_id,
            "content_type_counts": {},
            "is_complete": True,
            "truncated_tile_count": 0,
        })
        counts = region["content_type_counts"]
        if content_type in counts:
            raise ValueError(
                f"Kakao DB에 정규화 후 중복 유형이 있습니다: {region_id}/{content_type}"
            )
        counts[content_type] = count
        region["is_complete"] = region["is_complete"] and is_complete
        region["truncated_tile_count"] = max(region["truncated_tile_count"], truncated)

    expected_types = set(CONTENT_TYPES)
    for region_id, region in regions.items():
        actual_types = set(region["content_type_counts"])
        if actual_types != expected_types:
            raise ValueError(
                f"Kakao DB 콘텐츠 유형 불일치: {region_id}; "
                f"missing={sorted(expected_types - actual_types)}, "
                f"extra={sorted(actual_types - expected_types)}"
            )
        if require_complete and (
            not region["is_complete"] or region["truncated_tile_count"] != 0
        ):
            raise ValueError(f"Kakao DB 수집이 완전하지 않습니다: {region_id}")

    missing_regions = sorted(required - regions.keys())
    if missing_regions:
        raise ValueError("Kakao DB run에 필수 지역이 없습니다: " + ", ".join(missing_regions))
    canonical = {
        "run_id": run_id,
        "taxonomy_version": taxonomy_version,
        "collected_at": collected_at,
        "regions": [regions[key] for key in sorted(regions)],
    }
    checksum = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return KakaoSupplyRun(run_id, taxonomy_version, collected_at, regions, checksum)


def _read_supply_run(
    database_url: str, run_id: str
) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - optional dependency boundary
        raise ValueError("Postgres 조회에는 psycopg가 필요합니다. database extra를 설치하세요.") from exc
    metadata_query = """
        select run_id::text, taxonomy_version, collected_at, status
        from public.content_collection_runs
        where run_id = %s
    """
    rows_query = """
        select region_id, content_type, place_count, is_complete, truncated_tile_count
        from public.region_content_counts
        where run_id = %s
        order by region_id, content_type
    """
    try:
        with psycopg.connect(psycopg_connection_url(database_url)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(metadata_query, (run_id,))
                metadata_row = cursor.fetchone()
                cursor.execute(rows_query, (run_id,))
                rows = cursor.fetchall()
    except psycopg.Error as exc:
        raise ValueError(f"Kakao 공급 DB 조회에 실패했습니다: {exc}") from exc
    if metadata_row is None:
        raise ValueError(f"Kakao 수집 run을 찾을 수 없습니다: {run_id}")
    metadata = {
        "run_id": str(metadata_row[0]),
        "taxonomy_version": str(metadata_row[1]),
        "collected_at": str(metadata_row[2]),
        "status": str(metadata_row[3]),
    }
    return metadata, list(rows)


def _read_latest_complete_regions(
    database_url: str,
    *,
    required_region_ids: Sequence[str],
    require_complete: bool,
) -> KakaoSupplyRun:
    """Select the latest six-type collection independently per region."""
    region_ids = tuple(dict.fromkeys(str(value) for value in required_region_ids))
    regions: dict[str, dict[str, Any]] = {}
    collected_at_values: list[str] = []
    for region_id in region_ids:
        metadata, rows = _read_latest_supply_region(database_url, region_id)
        normalized = normalize_supply_run(
            metadata,
            rows,
            required_region_ids=(region_id,),
            require_complete=False,
            require_completed=False,
        )
        region = dict(normalized.regions[region_id])
        region["run_id"] = normalized.run_id
        region["taxonomy_version"] = normalized.taxonomy_version
        regions[region_id] = region
        collected_at_values.append(normalized.collected_at)
    canonical = {
        "selection": "latest-six-type-per-region",
        "regions": [regions[key] for key in sorted(regions)],
    }
    checksum = hashlib.sha256(
        json.dumps(canonical, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    return KakaoSupplyRun(
        run_id="latest-six-type-per-region",
        taxonomy_version="per-region",
        collected_at=max(collected_at_values),
        regions=regions,
        normalized_sha256=checksum,
    )


def _read_latest_supply_region(
    database_url: str, region_id: str
) -> tuple[dict[str, Any], list[tuple[Any, ...]]]:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - optional dependency boundary
        raise ValueError("psycopg is required for Kakao supply DB queries") from exc
    metadata_query = """
        select runs.run_id::text, runs.taxonomy_version, runs.collected_at, runs.status
        from public.content_collection_runs as runs
        join public.region_content_counts as counts on counts.run_id = runs.run_id
        where counts.region_id = %s
        group by runs.run_id, runs.taxonomy_version, runs.collected_at, runs.status
        having count(*) = 6
           and count(distinct counts.content_type) = 6
        order by runs.collected_at desc, runs.run_id desc
        limit 1
    """
    rows_query = """
        select region_id, content_type, place_count, is_complete, truncated_tile_count
        from public.region_content_counts
        where run_id = %s and region_id = %s
        order by content_type
    """
    try:
        with psycopg.connect(psycopg_connection_url(database_url)) as connection:
            with connection.cursor() as cursor:
                cursor.execute(metadata_query, (region_id,))
                metadata_row = cursor.fetchone()
                if metadata_row is None:
                    raise ValueError(f"No six-type Kakao collection exists for region_id={region_id}")
                cursor.execute(rows_query, (metadata_row[0], region_id))
                rows = cursor.fetchall()
    except psycopg.Error as exc:
        raise ValueError(f"Kakao supply DB query failed: {exc}") from exc
    return {
        "run_id": str(metadata_row[0]),
        "taxonomy_version": str(metadata_row[1]),
        "collected_at": str(metadata_row[2]),
        "status": str(metadata_row[3]),
    }, list(rows)


def _required_string(payload: Mapping[str, Any], field: str) -> str:
    value = payload.get(field)
    if value is None or not str(value).strip():
        raise ValueError(f"Kakao run {field}은 비어 있을 수 없습니다.")
    return str(value).strip()
