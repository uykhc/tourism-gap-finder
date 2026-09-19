"""PostgreSQL persistence for generated AI tourism reports."""

from __future__ import annotations

import json
from typing import Any

from ..kakao_places.content_store import psycopg_connection_url


class AIReportStore:
    """Store one current AI report envelope per region in Supabase PostgreSQL."""

    def __init__(self, database_url: str) -> None:
        if not database_url.strip():
            raise ValueError("CONTENT_DATABASE_URL is required for AI report storage")
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - optional dependency boundary
            raise ValueError("psycopg is required for AI report storage") from exc
        self._psycopg: Any = psycopg
        self._database_url = psycopg_connection_url(database_url)

    def save(self, *, region_id: str, envelope: dict[str, Any]) -> None:
        report = envelope.get("report")
        generator = envelope.get("generator")
        if len(region_id) != 5 or not region_id.isdigit():
            raise ValueError("region_id must be a five-digit code")
        if not isinstance(report, dict) or not isinstance(generator, dict):
            raise ValueError("AI report envelope requires report and generator objects")
        query = """
            insert into public.ai_reports (region_id, report_payload, generator)
            values (%s, %s::jsonb, %s::jsonb)
            on conflict (region_id) do update set
              report_payload = excluded.report_payload,
              generator = excluded.generator,
              generated_at = now(),
              updated_at = now()
        """
        try:
            with self._psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(
                        query,
                        (region_id, json.dumps(report, ensure_ascii=False), json.dumps(generator, ensure_ascii=False)),
                    )
        except self._psycopg.Error as exc:
            raise ValueError(f"AI report DB save failed: {exc}") from exc

    def load(self, region_id: str) -> dict[str, Any] | None:
        query = """
            select report_payload
            from public.ai_reports
            where region_id = %s
        """
        try:
            with self._psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, (region_id,))
                    row = cursor.fetchone()
        except self._psycopg.Error as exc:
            raise ValueError(f"AI report DB query failed: {exc}") from exc
        if row is None:
            return None
        value = row[0]
        if isinstance(value, str):
            value = json.loads(value)
        if not isinstance(value, dict):
            raise ValueError(f"AI report payload is invalid for region_id={region_id}")
        return value
