"""한국관광공사 국문 관광정보 서비스 클라이언트."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen
from xml.etree import ElementTree

from .models import TourismResource

DEFAULT_BASE_URL = (
    "https://apis.data.go.kr/B551011/KorService2/areaBasedList2"
)
DEFAULT_CODE_BASE_URL = (
    "https://apis.data.go.kr/B551011/KorService2/areaCode2"
)
SUCCESS_RESULT_CODE = "0000"


class TourApiError(RuntimeError):
    """TourAPI 호출 또는 응답 처리 실패."""


class TourApiClient:
    """`areaBasedList2`를 페이지 끝까지 조회하는 작은 HTTP 클라이언트."""

    def __init__(
        self,
        service_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        code_base_url: str = DEFAULT_CODE_BASE_URL,
        mobile_app: str = "HankkeutAnalysis",
        timeout_seconds: float = 20.0,
        page_size: int = 1000,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        if not service_key.strip():
            raise ValueError("TourAPI 서비스 키가 비어 있습니다.")
        if page_size <= 0:
            raise ValueError("page_size는 0보다 커야 합니다.")
        if timeout_seconds <= 0:
            raise ValueError("timeout_seconds는 0보다 커야 합니다.")

        # Encoding 키가 들어와도 urlencode에서 이중 인코딩되지 않도록 먼저
        # 디코딩한다. Decoding 키는 그대로 유지된다.
        self._service_key = unquote(service_key.strip())
        self._base_url = base_url
        self._code_base_url = code_base_url
        self._mobile_app = mobile_app
        self._timeout_seconds = timeout_seconds
        self._page_size = page_size
        self._opener = opener

    def fetch_region_resources(
        self,
        *,
        area_code: str,
        sigungu_code: str | None = None,
    ) -> list[TourismResource]:
        """지역의 모든 관광자원을 가져오고 contentid 중복을 제거한다.

        ``sigungu_code``를 생략하면 광역시·도 전체를 조회한다.
        """
        if not str(area_code).strip():
            raise ValueError("area_code가 비어 있습니다.")
        if sigungu_code is not None and not str(sigungu_code).strip():
            raise ValueError("sigungu_code가 비어 있습니다.")

        resources_by_id: dict[str, TourismResource] = {}
        resources_without_id: list[TourismResource] = []
        received_count = 0
        page_number = 1

        while True:
            payload = self._request_page(
                area_code=str(area_code),
                sigungu_code=(
                    str(sigungu_code) if sigungu_code is not None else None
                ),
                page_number=page_number,
            )
            page_items, total_count = self._parse_page(payload)
            received_count += len(page_items)

            for item in page_items:
                resource = _to_resource(item)
                if resource.content_id:
                    resources_by_id[resource.content_id] = resource
                else:
                    resources_without_id.append(resource)

            if not page_items or received_count >= total_count:
                break
            page_number += 1

        return [*resources_by_id.values(), *resources_without_id]

    def fetch_sigungu_codes(self, *, area_code: str) -> dict[str, str]:
        """KorService2의 시군구 코드와 이름을 공식 코드 API에서 조회한다."""
        if not str(area_code).strip():
            raise ValueError("area_code가 비어 있습니다.")

        codes: dict[str, str] = {}
        received_count = 0
        page_number = 1
        while True:
            payload = self._request_code_page(
                area_code=str(area_code),
                page_number=page_number,
            )
            items, total_count = self._parse_page(payload)
            received_count += len(items)
            for item in items:
                code = str(item.get("code") or "").strip()
                name = str(item.get("name") or "").strip()
                if code and name:
                    codes[code] = name
            if not items or received_count >= total_count:
                break
            page_number += 1
        return codes

    def _request_page(
        self,
        *,
        area_code: str,
        sigungu_code: str | None,
        page_number: int,
    ) -> dict[str, Any]:
        parameters: dict[str, Any] = {
            "serviceKey": self._service_key,
            "MobileOS": "ETC",
            "MobileApp": self._mobile_app,
            "_type": "json",
            "arrange": "A",
            "areaCode": area_code,
            "numOfRows": self._page_size,
            "pageNo": page_number,
        }
        if sigungu_code is not None:
            parameters["sigunguCode"] = sigungu_code
        return self._request_json(self._base_url, parameters)

    def _request_code_page(
        self,
        *,
        area_code: str,
        page_number: int,
    ) -> dict[str, Any]:
        return self._request_json(
            self._code_base_url,
            {
                "serviceKey": self._service_key,
                "MobileOS": "ETC",
                "MobileApp": self._mobile_app,
                "_type": "json",
                "areaCode": area_code,
                "numOfRows": 100,
                "pageNo": page_number,
            },
        )

    def _request_json(
        self,
        base_url: str,
        parameters: dict[str, Any],
    ) -> dict[str, Any]:
        query = urlencode(parameters)
        request = Request(
            f"{base_url}?{query}",
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
            raise TourApiError(
                f"TourAPI HTTP 오류({exc.code}): {detail}"
            ) from exc
        except URLError as exc:
            raise TourApiError(f"TourAPI 연결 실패: {exc.reason}") from exc
        except TimeoutError as exc:
            raise TourApiError("TourAPI 응답 시간이 초과되었습니다.") from exc

        try:
            decoded_body = raw_body.decode("utf-8")
            payload = json.loads(decoded_body)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            detail = _extract_error_message(raw_body)
            raise TourApiError(
                f"TourAPI가 JSON이 아닌 응답을 반환했습니다: {detail}"
            ) from exc

        if not isinstance(payload, dict):
            raise TourApiError("TourAPI JSON 최상위 값이 객체가 아닙니다.")
        return payload

    @staticmethod
    def _parse_page(
        payload: dict[str, Any],
    ) -> tuple[list[dict[str, Any]], int]:
        try:
            response = payload["response"]
            header = response["header"]
        except (KeyError, TypeError) as exc:
            raise TourApiError("TourAPI 응답에 response/header가 없습니다.") from exc

        result_code = str(header.get("resultCode", ""))
        if result_code != SUCCESS_RESULT_CODE:
            result_message = header.get("resultMsg", "알 수 없는 오류")
            raise TourApiError(
                f"TourAPI 오류({result_code}): {result_message}"
            )

        body = response.get("body") or {}
        if not isinstance(body, dict):
            raise TourApiError("TourAPI response/body 형식이 올바르지 않습니다.")

        try:
            total_count = int(body.get("totalCount", 0))
        except (TypeError, ValueError) as exc:
            raise TourApiError("TourAPI totalCount가 정수가 아닙니다.") from exc

        items_container = body.get("items") or {}
        if not isinstance(items_container, dict):
            return [], total_count

        raw_items = items_container.get("item", [])
        if isinstance(raw_items, dict):
            items = [raw_items]
        elif isinstance(raw_items, list):
            items = raw_items
        else:
            items = []

        return [item for item in items if isinstance(item, dict)], total_count


def _to_resource(item: dict[str, Any]) -> TourismResource:
    return TourismResource(
        content_id=str(item.get("contentid") or "").strip(),
        content_type_id=_optional_int(item.get("contenttypeid")),
        title=str(item.get("title") or "").strip(),
        address=str(item.get("addr1") or "").strip(),
        longitude=_optional_float(item.get("mapx")),
        latitude=_optional_float(item.get("mapy")),
    )


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
    """공공데이터포털의 XML 오류 응답에서 짧은 메시지를 꺼낸다."""
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
