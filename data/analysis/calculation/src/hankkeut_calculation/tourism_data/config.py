"""Local configuration loading without external dependencies."""

from __future__ import annotations

import os
import shlex
from collections.abc import Mapping
from pathlib import Path

SERVICE_KEY_ENV_NAME = "TOUR_API_SERVICE_KEY"
PORTFOLIO_SERVICE_KEY_ENV_NAME = "KOR_TOUR_API_SERVICE_KEY"
HUB_SERVICE_KEY_ENV_NAME = "HUB_TOUR_API_SERVICE_KEY"
VISITOR_SERVICE_KEY_ENV_NAME = "VISITOR_API_SERVICE_KEY"
KAKAO_REST_API_KEY_ENV_NAME = "KAKAO_REST_API_KEY"
DEFAULT_DOTENV_PATH = Path(".env")


def resolve_service_key(
    *,
    dotenv_path: Path = DEFAULT_DOTENV_PATH,
    environ: Mapping[str, str] | None = None,
    env_names: tuple[str, ...] = (SERVICE_KEY_ENV_NAME,),
) -> str | None:
    """Resolve a service key from the environment or a local ``.env`` file.

    The process environment takes precedence over ``.env``. Within each source,
    ``env_names`` defines the priority order. Only the requested keys are read,
    so unrelated values are not injected into the process environment.
    """
    if not env_names:
        raise ValueError("조회할 인증키 환경변수명이 없습니다.")

    source_environment = os.environ if environ is None else environ
    for env_name in env_names:
        environment_value = source_environment.get(env_name, "").strip()
        if environment_value:
            return environment_value

    try:
        lines = dotenv_path.read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return None

    dotenv_values: dict[str, tuple[str, int]] = {}
    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("export "):
            stripped = stripped.removeprefix("export ").lstrip()

        key, separator, raw_value = stripped.partition("=")
        normalized_key = key.strip()
        if not separator or normalized_key not in env_names:
            continue

        # 동일 키가 여러 번 선언되면 일반적인 dotenv 동작처럼 마지막 값을
        # 사용한다. 환경변수 우선순위는 파일에 적힌 순서와 무관하다.
        dotenv_values[normalized_key] = (raw_value, line_number)

    for env_name in env_names:
        candidate = dotenv_values.get(env_name)
        if candidate is None:
            continue
        raw_value, line_number = candidate
        parsed = _parse_dotenv_value(raw_value, line_number=line_number)
        if parsed:
            return parsed

    return None


def resolve_portfolio_service_key(
    *,
    dotenv_path: Path = DEFAULT_DOTENV_PATH,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """KorService2 키를 읽고 기존 공용 키로 대체한다."""
    return resolve_service_key(
        dotenv_path=dotenv_path,
        environ=environ,
        env_names=(PORTFOLIO_SERVICE_KEY_ENV_NAME, SERVICE_KEY_ENV_NAME),
    )


def resolve_hub_service_key(
    *,
    dotenv_path: Path = DEFAULT_DOTENV_PATH,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """중심 관광지 API 키를 읽고 기존 공용 키로 대체한다."""
    return resolve_service_key(
        dotenv_path=dotenv_path,
        environ=environ,
        env_names=(HUB_SERVICE_KEY_ENV_NAME, SERVICE_KEY_ENV_NAME),
    )


def resolve_visitor_service_key(
    *,
    dotenv_path: Path = DEFAULT_DOTENV_PATH,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """지역별 방문자 수 API 키를 읽는다.

    공공데이터포털의 서비스별 활용 권한이 필요하므로 KorService2 키와
    분리한다. 동일 키에 권한이 있으면 TOUR_API_SERVICE_KEY로도 대체한다.
    """
    return resolve_service_key(
        dotenv_path=dotenv_path,
        environ=environ,
        env_names=(VISITOR_SERVICE_KEY_ENV_NAME, SERVICE_KEY_ENV_NAME),
    )


def resolve_kakao_rest_api_key(
    *,
    dotenv_path: Path = DEFAULT_DOTENV_PATH,
    environ: Mapping[str, str] | None = None,
) -> str | None:
    """Resolve the Kakao Local API REST key without exposing it in output."""
    return resolve_service_key(
        dotenv_path=dotenv_path,
        environ=environ,
        env_names=(KAKAO_REST_API_KEY_ENV_NAME,),
    )


def _parse_dotenv_value(raw_value: str, *, line_number: int) -> str | None:
    try:
        values = shlex.split(raw_value, comments=True, posix=True)
    except ValueError as exc:
        raise ValueError(
            f".env {line_number}번째 줄의 인증키 따옴표가 올바르지 않습니다."
        ) from exc

    if not values:
        return None
    if len(values) != 1:
        raise ValueError(
            f".env {line_number}번째 줄의 인증키 형식이 올바르지 않습니다."
        )
    return values[0].strip() or None
