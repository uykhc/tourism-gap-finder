"""한국관광공사 빅데이터 지역별 방문자수 (DataLabService).

엔드포인트: /locgoRegnVisitrDDList  (기초지자체 일별 방문자)

2026-08-17 실호출로 확인한 응답 필드:

    signguCode  법정동 시군구 코드 (예: 11110)
    signguNm    시군구명
    daywkDivCd  요일 코드 (1=월 … 7=일)
    daywkDivNm  요일명
    touDivCd    1=현지인(a) / 2=외지인(b) / 3=외국인(c)
    touDivNm    구분명
    touNum      방문자 수 (실수 문자열)
    baseYmd     기준일자 (YYYYMMDD)

요청은 startYmd/endYmd 로 기간을 준다. 한 달치(약 24,000행)를 한 번에
받을 수 있어 numOfRows를 크게 잡고 월 단위로 수집한다.

**데이터 해석 주의**
이 '방문자'는 관광객과 같은 개념이 아니다. 이동통신 데이터로 일상생활권을
벗어나 일정 시간 머문 사람을 센 값이고, 일별 순방문자 기준이라 2박 3일
체류하면 3일에 걸쳐 잡힌다. 따라서 '관광 유입/활성화의 proxy'로만 쓴다.
현지인(touDivCd=1)은 관광 성과가 아니므로 제외하고, 외지인·외국인만 센다.
"""

from __future__ import annotations

import calendar
import json
import time
import urllib.parse
import urllib.request
from typing import Any

import pandas as pd

from ..config import RAW_DIR

URL = "https://apis.data.go.kr/B551011/DataLabService/locgoRegnVisitrDDList"
CACHE_DIR = RAW_DIR / "datalab"

LOCAL = "1"  # 현지인
OUTSIDER = "2"  # 외지인
FOREIGN = "3"  # 외국인


class DataLabError(RuntimeError):
    pass


class DataLabClient:
    def __init__(
        self,
        service_key: str,
        *,
        timeout_seconds: float = 120.0,
        page_size: int = 30_000,
    ) -> None:
        self._key = urllib.parse.unquote(service_key.strip())
        self._timeout = timeout_seconds
        self._page_size = page_size

    def fetch_month(self, year: int, month: int) -> list[dict[str, Any]]:
        """한 달치 일별 방문자. 디스크에 캐시한다."""
        CACHE_DIR.mkdir(parents=True, exist_ok=True)
        path = CACHE_DIR / f"{year:04d}{month:02d}.json"
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))

        last_day = calendar.monthrange(year, month)[1]
        items = self._request(
            {
                "startYmd": f"{year:04d}{month:02d}01",
                "endYmd": f"{year:04d}{month:02d}{last_day:02d}",
            }
        )
        path.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
        return items

    def _request(self, params: dict[str, Any]) -> list[dict[str, Any]]:
        collected: list[dict[str, Any]] = []
        page = 1
        while True:
            query = urllib.parse.urlencode(
                {
                    "serviceKey": self._key,
                    "MobileOS": "ETC",
                    "MobileApp": "TourGap",
                    "_type": "json",
                    "numOfRows": self._page_size,
                    "pageNo": page,
                    **params,
                }
            )
            request = urllib.request.Request(
                f"{URL}?{query}", headers={"Accept": "application/json"}
            )
            last: Exception | None = None
            for attempt in range(3):
                try:
                    with urllib.request.urlopen(
                        request, timeout=self._timeout
                    ) as response:
                        payload = json.loads(response.read().decode("utf-8"))
                    break
                except Exception as exc:  # noqa: BLE001
                    last = exc
                    time.sleep(2.0 * (attempt + 1))
            else:
                raise DataLabError(f"DataLab 요청 실패: {last}")

            body = payload["response"]["body"]
            container = body.get("items") or {}
            if not isinstance(container, dict):
                break
            raw = container.get("item", [])
            if isinstance(raw, dict):
                raw = [raw]
            collected.extend(raw)

            if len(collected) >= int(body.get("totalCount", 0)) or not raw:
                break
            page += 1
        return collected


def month_range(end_year: int, end_month: int, count: int) -> list[tuple[int, int]]:
    """(end_year, end_month)에서 거꾸로 count개월."""
    months = []
    year, month = end_year, end_month
    for _ in range(count):
        months.append((year, month))
        month -= 1
        if month == 0:
            year, month = year - 1, 12
    return sorted(months)


def to_frame(items: list[dict[str, Any]]) -> pd.DataFrame:
    frame = pd.DataFrame(items)
    if frame.empty:
        return frame
    frame["visitors"] = pd.to_numeric(frame["touNum"], errors="coerce")
    frame["datalab_code"] = frame["signguCode"].astype(str)
    frame["tour_div"] = frame["touDivCd"].astype(str)
    return frame[["datalab_code", "signguNm", "tour_div", "visitors", "baseYmd"]]
