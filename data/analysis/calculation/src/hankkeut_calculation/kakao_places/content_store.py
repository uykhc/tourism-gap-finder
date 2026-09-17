"""Postgres persistence for aggregated Kakao tourism-content collections."""

from __future__ import annotations

from typing import Any


def psycopg_connection_url(database_url: str) -> str:
    """Accept the SQLAlchemy URL used by the FastAPI service as well."""
    return database_url.replace("postgresql+psycopg://", "postgresql://", 1)


class KakaoContentStore:
    """Persist collection runs without retaining the source place list."""

    def __init__(self, database_url: str) -> None:
        if not database_url.strip():
            raise ValueError("CONTENT_DATABASE_URL이 비어 있습니다.")
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - depends on optional extra
            raise ValueError("Postgres 적재에는 psycopg가 필요합니다. database extra를 설치하세요.") from exc
        self._psycopg: Any = psycopg
        self._database_url = psycopg_connection_url(database_url)

    def start_run(self, *, taxonomy_version: str, collector_version: str, note: str | None) -> str:
        query = """
            insert into public.content_collection_runs
              (taxonomy_version, collector_version, status, note)
            values (%s, %s, 'running', %s)
            returning run_id
        """
        with self._psycopg.connect(self._database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (taxonomy_version, collector_version, note))
                run_id = cursor.fetchone()[0]
        return str(run_id)

    def save_region(
        self,
        *,
        run_id: str,
        region: dict[str, str],
        content_type_counts: dict[str, int],
        is_complete: bool,
        truncated_tile_count: int,
    ) -> None:
        region_query = """
            insert into public.regions
              (region_id, area_code, sigungu_code, province_name, region_name)
            values (%(region_id)s, %(area_code)s, %(sigungu_code)s, %(province_name)s, %(region_name)s)
            on conflict (region_id) do update set
              area_code = excluded.area_code,
              sigungu_code = excluded.sigungu_code,
              province_name = excluded.province_name,
              region_name = excluded.region_name,
              updated_at = now()
        """
        count_query = """
            insert into public.region_content_counts
              (run_id, region_id, content_type, place_count, is_complete, truncated_tile_count)
            values (%s, %s, %s, %s, %s, %s)
            on conflict (run_id, region_id, content_type) do update set
              place_count = excluded.place_count,
              is_complete = excluded.is_complete,
              truncated_tile_count = excluded.truncated_tile_count,
              collected_at = now()
        """
        rows = [
            (run_id, region["region_id"], content_type, count, is_complete, truncated_tile_count)
            for content_type, count in sorted(content_type_counts.items())
        ]
        if not rows:
            raise ValueError("저장할 콘텐츠 유형별 장소 수가 없습니다.")
        if any(not isinstance(count, int) or count < 0 for *_, count, _, _ in rows):
            raise ValueError("콘텐츠 유형별 장소 수는 0 이상의 정수여야 합니다.")
        with self._psycopg.connect(self._database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(region_query, region)
                cursor.executemany(count_query, rows)

    def finish_run(self, *, run_id: str, status: str, region_count: int, note: str | None = None) -> None:
        if status not in {"completed", "failed"}:
            raise ValueError("수집 실행 상태는 completed 또는 failed여야 합니다.")
        query = """
            update public.content_collection_runs
            set status = %s, region_count = %s, note = coalesce(%s, note)
            where run_id = %s
        """
        with self._psycopg.connect(self._database_url) as connection:
            with connection.cursor() as cursor:
                cursor.execute(query, (status, region_count, note, run_id))
