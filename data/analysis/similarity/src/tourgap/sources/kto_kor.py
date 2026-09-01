"""한국관광공사 국문 관광정보 서비스(KorService2) 클라이언트.

hankkeut-analysis의 TourApiClient를 옮겨 오되, 이번 분석에 필요한
lDongRegnCd / lDongSignguCd / lclsSystm1~3 / modifiedtime 을 함께 보존한다.
(이전 버전은 이 필드들을 버리고 있었다.)

공식 문서: https://www.data.go.kr/data/15101578/openapi.do
"""

from __future__ import annotations

import json
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

BASE = "https://apis.data.go.kr/B551011/KorService2"
SUCCESS = "0000"

# 참고용. 이번 분석의 주 축은 lclsSystm1이고 contentTypeId는 보조 지표다.
CONTENT_TYPES: dict[int, str] = {
    12: "관광지",
    14: "문화시설",
    15: "행사/공연/축제",
    25: "여행코스",
    28: "레포츠",
    32: "숙박",
    38: "쇼핑",
    39: "음식점",
}


class TourApiError(RuntimeError):
    """TourAPI 호출 또는 응답 처리 실패."""


class KorServiceClient:
    def __init__(
        self,
        service_key: str,
        *,
        mobile_app: str = "TourGap",
        timeout_seconds: float = 30.0,
        page_size: int = 1000,
        max_retries: int = 3,
        sleep_seconds: float = 0.1,
    ) -> None:
        if not service_key.strip():
            raise ValueError("서비스 키가 비어 있습니다.")
        # Encoding 키가 들어와도 urlencode에서 이중 인코딩되지 않도록 먼저
        # 디코딩한다. Decoding 키는 그대로 유지된다.
        self._key = unquote(service_key.strip())
        self._mobile_app = mobile_app
        self._timeout = timeout_seconds
        self._page_size = page_size
        self._max_retries = max_retries
        self._sleep = sleep_seconds

    # -- 공개 API ---------------------------------------------------------
    def fetch_provinces(self) -> list[dict[str, str]]:
        """17개 시도 코드."""
        items, _ = self._page("areaCode2", {"numOfRows": 100, "pageNo": 1})
        return [
            {"area_code": str(i["code"]), "province_name": str(i["name"])}
            for i in items
        ]

    def fetch_sigungu(self, area_code: str) -> list[dict[str, str]]:
        """한 시도의 시군구 코드."""
        items = self._all_pages("areaCode2", {"areaCode": area_code}, page_size=100)
        return [
            {
                "area_code": str(area_code),
                "sigungu_code": str(i["code"]),
                "sigungu_name": str(i["name"]),
            }
            for i in items
        ]

    def fetch_all_resources_by_type(self, content_type_id: int) -> list[dict[str, Any]]:
        """전국의 특정 콘텐츠 유형 전량.

        areaCode/sigunguCode로 걸러서 받으면 안 된다.
        전국 자원 48,858건 중 약 47%가 areacode/sigungucode가 비어 있어
        지역 필터를 걸면 그대로 누락된다(2026-08-17 확인).
        반면 lDongRegnCd/lDongSignguCd는 99.9%가 채워져 있으므로,
        전국을 유형별로 훑은 뒤 법정동 코드로 지역을 나누는 편이 정확하다.

        contentTypeId 8종의 totalCount 합은 전국 totalCount와 정확히
        일치하므로(48,858) 이 분할은 빠짐이 없다. 유형별로 나눠 받으면
        페이지 깊이가 얕아져 deep paging 누락 위험도 줄어든다.
        """
        items = self._all_pages(
            "areaBasedList2",
            {"contentTypeId": content_type_id, "arrange": "A"},
        )
        seen: dict[str, dict[str, Any]] = {}
        extras: list[dict[str, Any]] = []
        for item in items:
            record = normalize_resource(item)
            if record["content_id"]:
                seen[record["content_id"]] = record
            else:
                extras.append(record)
        return [*seen.values(), *extras]

    def fetch_lcls_codes(self, lcls1: str | None = None) -> list[dict[str, str]]:
        """신분류체계 코드. lcls1을 주면 그 하위 중분류를 준다."""
        params: dict[str, Any] = {}
        if lcls1:
            params["lclsSystm1"] = lcls1
        items = self._all_pages("lclsSystmCode2", params, page_size=100)
        return [
            {"code": str(i["code"]), "name": str(i["name"])}
            for i in items
            if i.get("code")
        ]

    # -- 내부 -------------------------------------------------------------
    def _all_pages(
        self,
        endpoint: str,
        params: dict[str, Any],
        *,
        page_size: int | None = None,
    ) -> list[dict[str, Any]]:
        size = page_size or self._page_size
        collected: list[dict[str, Any]] = []
        received = 0
        page = 1
        while True:
            items, total = self._page(
                endpoint, {**params, "numOfRows": size, "pageNo": page}
            )
            collected.extend(items)
            received += len(items)
            if not items or received >= total:
                break
            page += 1
            time.sleep(self._sleep)
        return collected

    def _page(
        self, endpoint: str, params: dict[str, Any]
    ) -> tuple[list[dict[str, Any]], int]:
        payload = self._request(endpoint, params)
        try:
            response = payload["response"]
            header = response["header"]
        except (KeyError, TypeError) as exc:
            raise TourApiError("응답에 response/header가 없습니다.") from exc

        code = str(header.get("resultCode", ""))
        if code != SUCCESS:
            raise TourApiError(
                f"TourAPI 오류({code}): {header.get('resultMsg', '알 수 없음')}"
            )

        body = response.get("body") or {}
        if not isinstance(body, dict):
            raise TourApiError("response/body 형식이 올바르지 않습니다.")

        try:
            total = int(body.get("totalCount", 0))
        except (TypeError, ValueError):
            total = 0

        container = body.get("items") or {}
        if not isinstance(container, dict):
            return [], total
        raw = container.get("item", [])
        if isinstance(raw, dict):
            raw = [raw]
        elif not isinstance(raw, list):
            raw = []
        return [i for i in raw if isinstance(i, dict)], total

    def _request(self, endpoint: str, params: dict[str, Any]) -> dict[str, Any]:
        query = urlencode(
            {
                "serviceKey": self._key,
                "MobileOS": "ETC",
                "MobileApp": self._mobile_app,
                "_type": "json",
                **params,
            }
        )
        url = f"{BASE}/{endpoint}?{query}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "TourGap/0.1",
            },
        )

        last_error: Exception | None = None
        for attempt in range(self._max_retries):
            try:
                with urlopen(request, timeout=self._timeout) as response:
                    body = response.read()
                break
            except HTTPError as exc:
                detail = _error_message(_safe_read(exc))
                # 키 미등록·할당량 초과는 재시도해도 소용없다.
                if exc.code in (401, 403):
                    raise TourApiError(f"HTTP {exc.code}: {detail}") from exc
                last_error = TourApiError(f"HTTP {exc.code}: {detail}")
            except (URLError, TimeoutError) as exc:
                last_error = TourApiError(f"연결 실패: {exc}")
            time.sleep(1.5 * (attempt + 1))
        else:
            raise last_error or TourApiError("요청에 실패했습니다.")

        try:
            return json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TourApiError(f"JSON이 아닌 응답: {_error_message(body)}") from exc


def normalize_resource(item: dict[str, Any]) -> dict[str, Any]:
    """areaBasedList2 item에서 분석에 쓰는 필드만 뽑는다.

    lDongRegnCd + lDongSignguCd 를 이어 붙여 KTO 실제 관광자원에 붙은
    5자리 지역 코드를 만든다. 예: 47 + 130 -> 47130 (경주시).
    """
    ldong = _ldong_code(
        str(item.get("lDongRegnCd") or "").strip(),
        str(item.get("lDongSignguCd") or "").strip(),
    )
    return {
        "content_id": str(item.get("contentid") or "").strip(),
        "content_type_id": _to_int(item.get("contenttypeid")),
        "title": str(item.get("title") or "").strip(),
        "address": str(item.get("addr1") or "").strip(),
        "area_code": str(item.get("areacode") or "").strip(),
        "sigungu_code": str(item.get("sigungucode") or "").strip(),
        "ldong_code": ldong,
        "lcls1": str(item.get("lclsSystm1") or "").strip(),
        "lcls2": str(item.get("lclsSystm2") or "").strip(),
        "lcls3": str(item.get("lclsSystm3") or "").strip(),
        "cat1": str(item.get("cat1") or "").strip(),
        "longitude": _to_float(item.get("mapx")),
        "latitude": _to_float(item.get("mapy")),
        "created_time": str(item.get("createdtime") or "").strip(),
        "modified_time": str(item.get("modifiedtime") or "").strip(),
    }


def _ldong_code(regn: str, signgu: str) -> str:
    """KTO lDong 계열 지역 코드 5자리를 만든다.

    보통은 시도 2자리 + 시군구 3자리로 나뉘어 온다(47 + 130 -> 47130).
    다만 세종특별자치시는 두 필드 모두에 5자리 전체 코드가 들어 있어
    (36110, 36110) 그냥 이으면 3611036110 이 된다. 길이로 구분한다.
    """
    if len(regn) == 2 and len(signgu) == 3:
        return regn + signgu
    if len(signgu) == 5:
        return signgu
    if len(regn) == 5:
        return regn
    return ""


def _to_int(value: Any) -> int | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return int(text)
    except ValueError:
        return None


def _to_float(value: Any) -> float | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _safe_read(exc: HTTPError) -> bytes:
    try:
        return exc.read()
    except Exception:
        return str(exc.reason).encode()


def _error_message(raw: bytes) -> str:
    """공공데이터포털의 XML/JSON 오류 응답에서 짧은 메시지를 꺼낸다."""
    text = raw.decode("utf-8", errors="replace").strip()
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
    try:
        payload = json.loads(text)
        header = payload.get("OpenAPI_ServiceResponse", {}).get("cmmMsgHeader", {})
        if header:
            return str(header.get("returnAuthMsg") or header.get("errMsg"))
    except (json.JSONDecodeError, AttributeError):
        pass
    return text[:200]
