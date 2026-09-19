"""Supabase storage for the non-AI inputs used to assemble a region report."""

from __future__ import annotations

import json
from typing import Any

from ..kakao_places.content_store import psycopg_connection_url


ARTIFACT_TYPES = frozenset({"peer_candidates", "relative_supply", "datalab_navigation"})


class RegionAnalysisArtifactStore:
    """Persist one current JSON artifact of each kind per municipality."""

    def __init__(self, database_url: str) -> None:
        if not database_url.strip():
            raise ValueError("CONTENT_DATABASE_URL is required for analysis artifact storage")
        try:
            import psycopg
        except ImportError as exc:  # pragma: no cover - optional dependency boundary
            raise ValueError("psycopg is required for analysis artifact storage") from exc
        self._psycopg: Any = psycopg
        self._database_url = psycopg_connection_url(database_url)

    def save(self, *, region_id: str, artifact_type: str, payload: dict[str, Any]) -> None:
        _validate(region_id, artifact_type, payload)
        query = """
            insert into public.region_analysis_artifacts (region_id, artifact_type, payload)
            values (%s, %s, %s::jsonb)
            on conflict (region_id, artifact_type) do update set
              payload = excluded.payload,
              updated_at = now()
        """
        try:
            with self._psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, (region_id, artifact_type, json.dumps(payload, ensure_ascii=False)))
        except self._psycopg.Error as exc:
            raise ValueError(f"Analysis artifact DB save failed: {exc}") from exc

    def load(self, *, region_id: str, artifact_type: str) -> dict[str, Any] | None:
        _validate(region_id, artifact_type, {})
        query = """
            select payload from public.region_analysis_artifacts
            where region_id = %s and artifact_type = %s
        """
        try:
            with self._psycopg.connect(self._database_url) as connection:
                with connection.cursor() as cursor:
                    cursor.execute(query, (region_id, artifact_type))
                    row = cursor.fetchone()
        except self._psycopg.Error as exc:
            raise ValueError(f"Analysis artifact DB query failed: {exc}") from exc
        if row is None:
            return None
        value = json.loads(row[0]) if isinstance(row[0], str) else row[0]
        if not isinstance(value, dict):
            raise ValueError(f"Analysis artifact payload is invalid for {region_id}/{artifact_type}")
        return value


def _validate(region_id: str, artifact_type: str, payload: dict[str, Any]) -> None:
    if len(region_id) != 5 or not region_id.isdigit():
        raise ValueError("region_id must be a five-digit code")
    if artifact_type not in ARTIFACT_TYPES:
        raise ValueError("unsupported analysis artifact type: " + artifact_type)
    if not isinstance(payload, dict):
        raise ValueError("analysis artifact payload must be an object")
