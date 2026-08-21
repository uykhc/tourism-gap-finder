"""한국관광공사 이동통신 기반 지역별 방문자 수 API 클라이언트."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen

DEFAULT_BASE_URL = (
    "https://apis.data.go.kr/B551011/DataLabService/locgoRegnVisitrDDList"
)
SUCCESS_RESULT_CODE = "0000"


class VisitorApiError(RuntimeError):
    """지역별 방문자 수 API 호출 또는 응답 처리 실패."""


@dataclass(frozen=True, slots=True)
class DailyRegionalVisitor:
    date_ymd: str
    region_name: str
    visitor_count: float
    visitor_type: str = ""


class VisitorApiClient:
    """기초지자체 일별 방문자 수를 페이지 끝까지 조회한다."""

    def __init__(
        self,
        service_key: str,
        *,
        base_url: str = DEFAULT_BASE_URL,
        mobile_app: str = "HankkeutAnalysis",
        timeout_seconds: float = 30.0,
        page_size: int = 1000,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        if not service_key.strip():
            raise ValueError("방문자 수 API 서비스 키가 비어 있습니다.")
        if timeout_seconds <= 0 or page_size <= 0:
            raise ValueError("timeout_seconds와 page_size는 0보다 커야 합니다.")
        self._service_key = unquote(service_key.strip())
        self._base_url = base_url
        self._mobile_app = mobile_app
        self._timeout_seconds = timeout_seconds
        self._page_size = page_size
        self._opener = opener

    def fetch_local_daily_visitors(
        self,
        *,
        start_ymd: str,
        end_ymd: str,
    ) -> list[DailyRegionalVisitor]:
        _validate_date_range(start_ymd, end_ymd)
        records: list[DailyRegionalVisitor] = []
        received_count = 0
        page_number = 1
        while True:
            payload = self._request_page(
                start_ymd=start_ymd,
                end_ymd=end_ymd,
                page_number=page_number,
            )
            items, total_count = self._parse_page(payload)
            received_count += len(items)
            records.extend(_to_daily_visitor(item) for item in items)
            if not items or received_count >= total_count:
                break
            page_number += 1
        return records

    def _request_page(
        self,
        *,
        start_ymd: str,
        end_ymd: str,
        page_number: int,
    ) -> dict[str, Any]:
        query = urlencode(
            {
                "serviceKey": self._service_key,
                "MobileOS": "ETC",
                "MobileApp": self._mobile_app,
                "_type": "json",
                "startYmd": start_ymd,
                "endYmd": end_ymd,
                "numOfRows": self._page_size,
                "pageNo": page_number,
            }
        )
        request = Request(
            f"{self._base_url}?{query}",
            headers={"Accept": "application/json", "User-Agent": "HankkeutAnalysis/0.1"},
        )
        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise VisitorApiError(f"방문자 수 API HTTP 오류({exc.code})") from exc
        except URLError as exc:
            raise VisitorApiError(f"방문자 수 API 연결 실패: {exc.reason}") from exc
        except (TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise VisitorApiError("방문자 수 API 응답을 읽지 못했습니다.") from exc
        if not isinstance(payload, dict):
            raise VisitorApiError("방문자 수 API JSON 최상위 값이 객체가 아닙니다.")
        return payload

    @staticmethod
    def _parse_page(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
        try:
            response = payload["response"]
            header = response["header"]
        except (KeyError, TypeError) as exc:
            raise VisitorApiError("방문자 수 API 응답에 response/header가 없습니다.") from exc
        if str(header.get("resultCode", "")) != SUCCESS_RESULT_CODE:
            raise VisitorApiError(
                "방문자 수 API 오류: " + str(header.get("resultMsg", "알 수 없는 오류"))
            )
        body = response.get("body") or {}
        try:
            total_count = int(body.get("totalCount", 0))
        except (AttributeError, TypeError, ValueError) as exc:
            raise VisitorApiError("방문자 수 API totalCount 형식이 올바르지 않습니다.") from exc
        items_container = body.get("items") or {}
        raw_items = items_container.get("item", []) if isinstance(items_container, dict) else []
        if isinstance(raw_items, dict):
            raw_items = [raw_items]
        return ([item for item in raw_items if isinstance(item, dict)], total_count)


def _validate_date_range(start_ymd: str, end_ymd: str) -> None:
    try:
        start = datetime.strptime(start_ymd, "%Y%m%d").date()
        end = datetime.strptime(end_ymd, "%Y%m%d").date()
    except ValueError as exc:
        raise ValueError("start_ymd와 end_ymd는 YYYYMMDD 형식이어야 합니다.") from exc
    if start > end or end > date.today():
        raise ValueError("방문자 수 조회 기간이 올바르지 않습니다.")


def _to_daily_visitor(item: dict[str, Any]) -> DailyRegionalVisitor:
    region_name = _first_text(item, "areaNm", "areaName", "signguNm", "regionName")
    date_ymd = _first_text(item, "baseYmd", "baseDate", "ymd")
    raw_count = _first_text(item, "touNum", "visitorCount", "visitrCnt", "visitCount")
    if not region_name or not date_ymd or not raw_count:
        raise VisitorApiError("방문자 수 응답의 지역명·일자·방문자 수 필드가 없습니다.")
    try:
        visitor_count = float(raw_count.replace(",", ""))
    except ValueError as exc:
        raise VisitorApiError("방문자 수 응답의 방문자 수가 숫자가 아닙니다.") from exc
    if visitor_count < 0:
        raise VisitorApiError("방문자 수 응답의 방문자 수가 음수입니다.")
    return DailyRegionalVisitor(
        date_ymd=date_ymd,
        region_name=region_name,
        visitor_count=visitor_count,
        visitor_type=_first_text(item, "touDivNm", "visitorType", "visitrTypeNm"),
    )


def _first_text(item: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = item.get(key)
        if value is not None and str(value).strip():
            return str(value).strip()
    return ""
