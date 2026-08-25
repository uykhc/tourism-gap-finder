"""통계청 SGIS OpenAPI3 클라이언트.

- 인증:   /auth/authentication.json      (consumer_key, consumer_secret)
- 인구:   /stats/population.json         (총조사 주요지표)
- 경계:   /boundary/hadmarea.geojson     (면적·중심점 계산용)

SGIS adm_cd는 KTO lDong 계열 지역 코드와 완전히 같지 않다. 구조 변수
제공자는 SGIS 응답을 시도명·시군구명과 보정표 기준으로 분석 region_id에
붙인다.

면적은 GeoJSON 좌표(UTM-K, EPSG:5179, 단위 m)에 shoelace 공식을 적용해
구한다. shapely/pyproj 없이 계산하기 위한 선택이다.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

from ..config import RAW_DIR

DEFAULT_API_BASE_URL = "https://sgisapi.mods.go.kr/OpenAPI3"
LEGACY_API_BASE_URL = "https://sgisapi.kostat.go.kr/OpenAPI3"


def _api_url(path: str) -> str:
    """SGIS OpenAPI URL.

    최신 SGIS 개발지원센터의 newOpenApi 문서는 ``sgisapi.mods.go.kr``를
    안내하지만, 구 문서와 일부 예제에는 ``sgisapi.kostat.go.kr``가 남아
    있다. 기본값은 최신 문서를 따르고, 필요하면 환경변수로 고정한다.
    """
    base = os.environ.get("SGIS_API_BASE_URL", "").strip() or DEFAULT_API_BASE_URL
    base = base.rstrip("/")
    return f"{base}/{path.lstrip('/')}"


AUTH_URL = _api_url("auth/authentication.json")
POPULATION_URL = _api_url("stats/population.json")
COMPANY_URL = _api_url("stats/company.json")
INDUSTRY_CODE_URL = _api_url("stats/industrycode.json")
BOUNDARY_URL = _api_url("boundary/hadmarea.geojson")


class SgisError(RuntimeError):
    """SGIS 호출 실패."""


class SgisClient:
    def __init__(
        self,
        consumer_key: str,
        consumer_secret: str,
        *,
        timeout_seconds: float = 30.0,
        cache_dir: Path | None = None,
    ) -> None:
        self._key = consumer_key
        self._secret = consumer_secret
        self._timeout = timeout_seconds
        self._token: str | None = None
        self._cache_dir = cache_dir if cache_dir is not None else RAW_DIR / "sgis"

    def _access_token(self) -> str:
        if self._token:
            return self._token
        payload = self._get(
            AUTH_URL,
            {"consumer_key": self._key, "consumer_secret": self._secret},
            authenticated=False,
        )
        result = payload.get("result") or {}
        token = result.get("accessToken")
        if not token:
            raise SgisError(f"SGIS 인증 실패: {payload.get('errMsg', payload)}")
        self._token = str(token)
        return self._token

    def fetch_population(
        self, *, year: str, adm_cd: str | None = None, low_search: str = "1"
    ) -> list[dict[str, Any]]:
        """총조사 주요지표.

        adm_cd를 생략하고 low_search=1이면 전국의 시도 목록이 나온다.
        시도 코드(2자리) + low_search=1 이면 그 시도의 시군구가 나온다.
        """
        params: dict[str, Any] = {"year": year, "low_search": low_search}
        if adm_cd:
            params["adm_cd"] = adm_cd
        payload = self._get(POPULATION_URL, params)
        if str(payload.get("errCd", 0)) not in ("0", "0.0"):
            raise SgisError(f"SGIS 인구 조회 실패: {payload.get('errMsg')}")
        result = payload.get("result") or []
        return result if isinstance(result, list) else [result]

    def fetch_boundary(
        self, *, year: str, adm_cd: str | None = None, low_search: str = "1"
    ) -> dict[str, Any]:
        params: dict[str, Any] = {"year": year, "low_search": low_search}
        if adm_cd:
            params["adm_cd"] = adm_cd
        return self._get(BOUNDARY_URL, params)

    def fetch_company(
        self,
        *,
        year: str,
        adm_cd: str | None = None,
        class_code: str | None = None,
        low_search: str = "1",
    ) -> list[dict[str, Any]]:
        """사업체통계. class_code는 KSIC 대분류 코드다."""
        params: dict[str, Any] = {"year": year, "low_search": low_search}
        if adm_cd:
            params["adm_cd"] = adm_cd
        if class_code:
            params["class_code"] = class_code
        payload = self._get(COMPANY_URL, params)
        if str(payload.get("errCd", 0)) not in ("0", "0.0"):
            raise SgisError(f"SGIS 사업체 조회 실패: {payload.get('errMsg')}")
        result = payload.get("result") or []
        return result if isinstance(result, list) else [result]

    def fetch_industry_codes(
        self, *, class_deg: str, class_code: str | None = None
    ) -> list[dict[str, Any]]:
        """SGIS 산업분류 코드 원 응답."""
        params: dict[str, Any] = {"class_deg": class_deg}
        if class_code:
            params["class_code"] = class_code
        payload = self._get(INDUSTRY_CODE_URL, params)
        if str(payload.get("errCd", 0)) not in ("0", "0.0"):
            raise SgisError(f"SGIS 산업분류 조회 실패: {payload.get('errMsg')}")
        result = payload.get("result") or []
        return result if isinstance(result, list) else [result]

    # -- 내부 -------------------------------------------------------------
    def _get(
        self,
        url: str,
        params: dict[str, Any],
        *,
        authenticated: bool = True,
    ) -> dict[str, Any]:
        """디스크 캐시 -> 네트워크. 토큰이 만료되면 한 번 재발급한다."""
        cache_path = self._cache_path(url, params) if authenticated else None
        if cache_path is not None and cache_path.exists():
            return json.loads(cache_path.read_text(encoding="utf-8"))

        payload: dict[str, Any] | None = None
        for refreshed in (False, True):
            if refreshed:
                # accessToken은 수명이 짧다. 만료로 보이면 한 번 다시 받는다.
                self._token = None
            query = dict(params)
            if authenticated:
                query["accessToken"] = self._access_token()
            payload = self._fetch(f"{url}?{urllib.parse.urlencode(query)}")
            if not authenticated or not _is_auth_error(payload):
                break

        if payload is None:
            raise SgisError("SGIS 응답이 비어 있습니다.")
        if authenticated and _is_auth_error(payload):
            raise SgisError(f"SGIS 인증 실패: {payload.get('errMsg')}")

        if cache_path is not None:
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_text(
                json.dumps(payload, ensure_ascii=False), encoding="utf-8"
            )
        return payload

    def _fetch(self, full_url: str) -> dict[str, Any]:
        request = urllib.request.Request(
            full_url, headers={"User-Agent": "TourGap/0.1"}
        )
        last: Exception | None = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=self._timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except Exception as exc:  # noqa: BLE001 - 네트워크 예외 전반
                last = exc
                time.sleep(1.5 * (attempt + 1))
        raise SgisError(f"SGIS 요청 실패: {last}")

    def _cache_path(self, url: str, params: dict[str, Any]) -> Path | None:
        if self._cache_dir is None:
            return None
        name = url.rstrip("/").split("/")[-1].replace(".", "_")
        key = "_".join(
            f"{k}-{v}" for k, v in sorted(params.items()) if k != "accessToken"
        )
        digest = hashlib.sha1(key.encode()).hexdigest()[:10]
        return self._cache_dir / f"{name}_{key[:40]}_{digest}.json"


def _is_auth_error(payload: dict[str, Any]) -> bool:
    code = str(payload.get("errCd", "0"))
    return code in {"-401", "-100"} or "인증" in str(payload.get("errMsg", ""))


def polygon_area_m2(rings: list[list[list[float]]]) -> float:
    """shoelace 공식. 첫 ring은 외곽, 나머지는 구멍으로 본다."""
    if not rings:
        return 0.0
    total = _ring_area(rings[0])
    for hole in rings[1:]:
        total -= _ring_area(hole)
    return max(total, 0.0)


def _ring_area(ring: list[list[float]]) -> float:
    if len(ring) < 3:
        return 0.0
    total = 0.0
    for index in range(len(ring)):
        x1, y1 = ring[index][0], ring[index][1]
        x2, y2 = ring[(index + 1) % len(ring)][0], ring[(index + 1) % len(ring)][1]
        total += x1 * y2 - x2 * y1
    return abs(total) / 2.0


def geometry_area_m2(geometry: dict[str, Any]) -> float:
    kind = geometry.get("type")
    coordinates = geometry.get("coordinates") or []
    if kind == "Polygon":
        return polygon_area_m2(coordinates)
    if kind == "MultiPolygon":
        return sum(polygon_area_m2(part) for part in coordinates)
    return 0.0
