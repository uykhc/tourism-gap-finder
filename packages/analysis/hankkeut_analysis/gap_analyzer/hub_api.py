"""한국관광공사 기초지자체 중심 관광지 정보 API 클라이언트."""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from collections.abc import Iterable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .models import HubTouristSpot

DEFAULT_HUB_BASE_URL = (
    "https://apis.data.go.kr/B551011/LocgoHubTarService1/areaBasedList1"
)
SUCCESS_RESULT_CODE = "0000"
MAX_HUB_SPOTS = 100


class HubTourApiError(RuntimeError):
    """중심 관광지 API 호출 또는 응답 처리 실패."""


class HubTourApiClient:
    """기초지자체의 중심 관광지 순위를 조회한다."""

    def __init__(
        self,
        service_key: str,
        *,
        base_url: str = DEFAULT_HUB_BASE_URL,
        mobile_app: str = "HankkeutAnalysis",
        timeout_seconds: float = 20.0,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        if not service_key.strip():
            raise ValueError("TourAPI 서비스 키가 비어 있습니다.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds는 0보다 커야 합니다.")

        self._service_key = unquote(service_key.strip())
        self._base_url = base_url
        self._mobile_app = mobile_app
        self._timeout_seconds = timeout_seconds
        self._opener = opener

    def fetch_top_spots(
        self,
        *,
        base_year_month: str,
        area_code: str,
        sigungu_code: str,
        limit: int = 5,
        category_large: str | None = None,
        category_middle: str | None = None,
        excluded_category_middle: Iterable[str] = (),
    ) -> list[HubTouristSpot]:
        """API 순위를 기준으로 상위 ``limit``개 중심 관광지를 반환한다."""
        _validate_query(
            base_year_month=base_year_month,
            area_code=area_code,
            sigungu_code=sigungu_code,
            limit=limit,
        )
        payload = self._request_page(
            base_year_month=base_year_month,
            area_code=str(area_code),
            sigungu_code=str(sigungu_code),
            # 이 API가 제공하는 순위 전체(최대 100건)를 한 번에 받은 뒤
            # 정렬해야 응답 순서와 무관하게 정확한 상위 N개를 고를 수 있다.
            page_size=MAX_HUB_SPOTS,
        )
        items = self._parse_items(payload)
        spots: list[HubTouristSpot] = []
        for index, item in enumerate(items, start=1):
            spot = _to_hub_spot(item, fallback_rank=index)
            if not spot.name:
                fields = ", ".join(sorted(item))
                raise HubTourApiError(
                    "중심 관광지명(hubTatsNm)을 응답에서 찾지 못했습니다. "
                    f"응답 필드: {fields or '없음'}"
                )
            spots.append(spot)
        # 명세상 순위순 응답이지만, 순위 필드를 기준으로 다시 정렬해 응답
        # 순서가 바뀌어도 상위 N개 선정 규칙을 보존한다.
        spots.sort(key=lambda spot: spot.rank)
        if category_large is not None:
            normalized_category = category_large.strip()
            if not normalized_category:
                raise ValueError("category_large가 비어 있습니다.")
            spots = [
                spot
                for spot in spots
                if spot.category_large == normalized_category
            ]
        if category_middle is not None:
            normalized_middle = category_middle.strip()
            if not normalized_middle:
                raise ValueError("category_middle이 비어 있습니다.")
            spots = [
                spot
                for spot in spots
                if spot.category_middle == normalized_middle
            ]
        excluded_middle = {
            category.strip()
            for category in excluded_category_middle
            if category.strip()
        }
        if excluded_middle:
            spots = [
                spot
                for spot in spots
                if spot.category_middle not in excluded_middle
            ]
        return spots[:limit]

    def _request_page(
        self,
        *,
        base_year_month: str,
        area_code: str,
        sigungu_code: str,
        page_size: int,
    ) -> dict[str, Any]:
        query = urlencode(
            {
                "serviceKey": self._service_key,
                "pageNo": 1,
                "numOfRows": page_size,
                "MobileOS": "ETC",
                "MobileApp": self._mobile_app,
                "baseYm": base_year_month,
                "areaCd": area_code,
                "signguCd": sigungu_code,
                "_type": "json",
            }
        )
        request = Request(
            f"{self._base_url}?{query}",
            headers={
                "Accept": "application/json",
                "User-Agent": "HankkeutAnalysis/0.1",
            },
        )

        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                raw_body = response.read()
        except HTTPError as exc:
            detail = _read_http_error(exc)
            raise HubTourApiError(
                f"중심 관광지 API HTTP 오류({exc.code}): {detail}"
            ) from exc
        except URLError as exc:
            raise HubTourApiError(
                f"중심 관광지 API 연결 실패: {exc.reason}"
            ) from exc
        except TimeoutError as exc:
            raise HubTourApiError(
                "중심 관광지 API 응답 시간이 초과되었습니다."
            ) from exc

        try:
            decoded_body = raw_body.decode("utf-8")
            payload = json.loads(decoded_body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            detail = _extract_error_message(raw_body)
            raise HubTourApiError(
                f"중심 관광지 API가 JSON이 아닌 응답을 반환했습니다: {detail}"
            ) from exc

        if not isinstance(payload, dict):
            raise HubTourApiError("중심 관광지 API JSON 최상위 값이 객체가 아닙니다.")
        return payload

    @staticmethod
    def _parse_items(payload: dict[str, Any]) -> list[dict[str, Any]]:
        try:
            response = payload["response"]
            header = response["header"]
        except (KeyError, TypeError) as exc:
            raise HubTourApiError(
                "중심 관광지 API 응답에 response/header가 없습니다."
            ) from exc

        result_code = str(header.get("resultCode", ""))
        if result_code != SUCCESS_RESULT_CODE:
            result_message = header.get("resultMsg", "알 수 없는 오류")
            raise HubTourApiError(
                f"중심 관광지 API 오류({result_code}): {result_message}"
            )

        body = response.get("body") or {}
        if not isinstance(body, dict):
            raise HubTourApiError(
                "중심 관광지 API response/body 형식이 올바르지 않습니다."
            )

        items_container = body.get("items") or {}
        if not isinstance(items_container, dict):
            return []

        raw_items = items_container.get("item", [])
        if isinstance(raw_items, dict):
            items = [raw_items]
        elif isinstance(raw_items, list):
            items = raw_items
        else:
            items = []
        return [item for item in items if isinstance(item, dict)]


def _validate_query(
    *,
    base_year_month: str,
    area_code: str,
    sigungu_code: str,
    limit: int,
) -> None:
    if not re.fullmatch(r"\d{6}", str(base_year_month)):
        raise ValueError("base_year_month는 YYYYMM 형식이어야 합니다.")
    month = int(str(base_year_month)[4:])
    if not 1 <= month <= 12:
        raise ValueError("base_year_month의 월은 01부터 12까지여야 합니다.")
    if not str(area_code).strip():
        raise ValueError("area_code가 비어 있습니다.")
    if not str(sigungu_code).strip():
        raise ValueError("sigungu_code가 비어 있습니다.")
    if not 1 <= limit <= MAX_HUB_SPOTS:
        raise ValueError(f"limit은 1부터 {MAX_HUB_SPOTS}까지여야 합니다.")


def _to_hub_spot(
    item: dict[str, Any],
    *,
    fallback_rank: int,
) -> HubTouristSpot:
    rank = _optional_int(_first_value(item, "hubRank", "hubTatsRank", "rank"))
    if rank is None or rank <= 0:
        rank = fallback_rank

    return HubTouristSpot(
        rank=rank,
        tourist_spot_code=_text(_first_value(item, "hubTatsCd")),
        name=_text(_first_value(item, "hubTatsNm", "hubNm", "title")),
        category_large=_text(
            _first_value(item, "hubCtgryLclsNm", "hubCtgryLclsName")
        ),
        category_middle=_text(
            _first_value(item, "hubCtgryMclsNm", "hubCtgryMclsName")
        ),
        category_small=_text(
            _first_value(item, "hubCtgrySclsNm", "hubCtgrySclsName")
        ),
        longitude=_optional_float(
            _first_value(item, "hubMapX", "mapX", "mapx")
        ),
        latitude=_optional_float(
            _first_value(item, "hubMapY", "mapY", "mapy")
        ),
        raw_fields=dict(item),
    )


def _first_value(item: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip() != "":
            return value
    return None


def _text(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _optional_int(value: Any) -> int | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return int(str(value))
    except ValueError:
        return None


def _optional_float(value: Any) -> float | None:
    if value is None or str(value).strip() == "":
        return None
    try:
        return float(str(value))
    except ValueError:
        return None


def _read_http_error(exc: HTTPError) -> str:
    try:
        return _extract_error_message(exc.read())
    except Exception:
        return str(exc.reason)


def _extract_error_message(raw_body: bytes) -> str:
    text = raw_body.decode("utf-8", errors="replace").strip()
    if not text:
        return "빈 응답"

    try:
        root = ElementTree.fromstring(text)
        for tag in ("returnAuthMsg", "resultMsg", "errMsg", "returnReasonCode"):
            node = root.find(f".//{tag}")
            if node is not None and node.text:
                return node.text.strip()
    except ElementTree.ParseError:
        pass
    return text[:200]
