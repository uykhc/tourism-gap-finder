"""지역별 관광 자원 수요·관광 수요 강도 API 클라이언트."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import unquote, urlencode
from urllib.request import Request, urlopen

RESOURCE_BASE_URL = "https://apis.data.go.kr/B551011/AreaTarResDemService"
INTENSITY_BASE_URL = "https://apis.data.go.kr/B551011/AreaTarDemDsService"
SUCCESS_RESULT_CODE = "0000"


class TourismDemandApiError(RuntimeError):
    """관광 수요 지수 API 호출 또는 응답 처리 실패."""


@dataclass(frozen=True, slots=True)
class TourismDemandRecord:
    base_ym: str
    sigungu_code: str
    sigungu_name: str
    index_code: str
    index_name: str
    value: float


class TourismDemandApiClient:
    """월별 관광 수요 지수의 전체 지표를 시군구 단위로 조회한다."""

    def __init__(
        self,
        service_key: str,
        *,
        mobile_app: str = "HankkeutAnalysis",
        timeout_seconds: float = 30.0,
        page_size: int = 1000,
        opener: Callable[..., Any] = urlopen,
    ) -> None:
        if not service_key.strip():
            raise ValueError("관광 수요 지수 API 서비스 키가 비어 있습니다.")
        if timeout_seconds <= 0 or page_size <= 0:
            raise ValueError("timeout_seconds와 page_size는 0보다 커야 합니다.")
        self._service_key = unquote(service_key.strip())
        self._mobile_app = mobile_app
        self._timeout_seconds = timeout_seconds
        self._page_size = page_size
        self._opener = opener

    def fetch_all_scores(self, *, base_ym: str, area_code: str) -> dict[str, dict[str, TourismDemandRecord]]:
        """4개 전체 지표(11·12·21·22)를 한 달·광역 지역에서 모두 읽는다."""
        _validate_base_ym(base_ym)
        specs = {
            "resource_service": (RESOURCE_BASE_URL, "areaTarSvcDemList", "tarSvcDemIxCd", "tarSvcDemIxVal", "tarSvcDemIxNm", "11"),
            "resource_culture": (RESOURCE_BASE_URL, "areaCulResDemList", "culResDemIxCd", "culResDemIxVal", "culResDemIxNm", "12"),
            "intensity_stay": (INTENSITY_BASE_URL, "areaTarSjrnDsList", "tarSjrnDsIxCd", "tarSjrnDsIxVal", "tarSjrnDsIxNm", "21"),
            "intensity_spend": (INTENSITY_BASE_URL, "areaTarExpDsList", "tarExpDsIxCd", "tarExpDsIxVal", "tarExpDsIxNm", "22"),
        }
        return {
            key: self._fetch_indicator(
                base_url=base_url,
                operation=operation,
                code_parameter=code_parameter,
                value_field=value_field,
                name_field=name_field,
                index_code=index_code,
                base_ym=base_ym,
                area_code=area_code,
            )
            for key, (base_url, operation, code_parameter, value_field, name_field, index_code) in specs.items()
        }

    def _fetch_indicator(
        self,
        *,
        base_url: str,
        operation: str,
        code_parameter: str,
        value_field: str,
        name_field: str,
        index_code: str,
        base_ym: str,
        area_code: str,
    ) -> dict[str, TourismDemandRecord]:
        records: dict[str, TourismDemandRecord] = {}
        received_count = 0
        page_number = 1
        while True:
            payload = self._request_page(
                url=f"{base_url}/{operation}",
                parameters={
                    "baseYm": base_ym,
                    "areaCd": area_code,
                    code_parameter: index_code,
                    "pageNo": page_number,
                },
            )
            items, total_count = self._parse_page(payload)
            received_count += len(items)
            for item in items:
                record = _to_record(item, index_code, value_field, name_field)
                records[record.sigungu_code] = record
            if not items or received_count >= total_count:
                break
            page_number += 1
        return records

    def _request_page(self, *, url: str, parameters: dict[str, Any]) -> dict[str, Any]:
        query = urlencode(
            {
                "serviceKey": self._service_key,
                "MobileOS": "ETC",
                "MobileApp": self._mobile_app,
                "_type": "json",
                "numOfRows": self._page_size,
                **parameters,
            }
        )
        request = Request(
            f"{url}?{query}",
            headers={"Accept": "application/json", "User-Agent": "HankkeutAnalysis/0.1"},
        )
        try:
            with self._opener(request, timeout=self._timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            raise TourismDemandApiError(f"관광 수요 지수 API HTTP 오류({exc.code})") from exc
        except URLError as exc:
            raise TourismDemandApiError(f"관광 수요 지수 API 연결 실패: {exc.reason}") from exc
        except (TimeoutError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TourismDemandApiError("관광 수요 지수 API 응답을 읽지 못했습니다.") from exc
        if not isinstance(payload, dict):
            raise TourismDemandApiError("관광 수요 지수 API JSON 최상위 값이 객체가 아닙니다.")
        return payload

    @staticmethod
    def _parse_page(payload: dict[str, Any]) -> tuple[list[dict[str, Any]], int]:
        try:
            response = payload["response"]
            header = response["header"]
        except (KeyError, TypeError) as exc:
            raise TourismDemandApiError("관광 수요 지수 API 응답에 response/header가 없습니다.") from exc
        if str(header.get("resultCode", "")) != SUCCESS_RESULT_CODE:
            raise TourismDemandApiError("관광 수요 지수 API 오류: " + str(header.get("resultMsg", "알 수 없는 오류")))
        body = response.get("body") or {}
        try:
            total_count = int(body.get("totalCount", 0))
        except (AttributeError, TypeError, ValueError) as exc:
            raise TourismDemandApiError("관광 수요 지수 API totalCount 형식이 올바르지 않습니다.") from exc
        items = (body.get("items") or {}).get("item", [])
        if isinstance(items, dict):
            items = [items]
        return ([item for item in items if isinstance(item, dict)], total_count)


def previous_months(*, maximum_count: int, today: date | None = None) -> tuple[str, ...]:
    if maximum_count < 1:
        raise ValueError("maximum_count는 1 이상이어야 합니다.")
    reference = today or date.today()
    year, month = reference.year, reference.month
    values = []
    for _ in range(maximum_count):
        values.append(f"{year:04d}{month:02d}")
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return tuple(values)


def _validate_base_ym(value: str) -> None:
    if len(value) != 6 or not value.isdigit() or not 1 <= int(value[4:]) <= 12:
        raise ValueError("base_ym은 YYYYMM 형식이어야 합니다.")


def _to_record(item: dict[str, Any], index_code: str, value_field: str, name_field: str) -> TourismDemandRecord:
    try:
        value = float(str(item[value_field]).replace(",", ""))
    except (KeyError, TypeError, ValueError) as exc:
        raise TourismDemandApiError(f"관광 수요 지수 응답의 {value_field} 값이 올바르지 않습니다.") from exc
    sigungu_code = str(item.get("signguCd", "")).strip()
    if not sigungu_code:
        raise TourismDemandApiError("관광 수요 지수 응답에 signguCd가 없습니다.")
    return TourismDemandRecord(
        base_ym=str(item.get("baseYm", "")).strip(),
        sigungu_code=sigungu_code,
        sigungu_name=str(item.get("signguNm", "")).strip(),
        index_code=str(item.get("tarSvcDemIxCd") or item.get("culResDemIxCd") or item.get("tarSjrnDsIxCd") or item.get("tarExpDsIxCd") or index_code),
        index_name=str(item.get(name_field, "")).strip(),
        value=value,
    )
