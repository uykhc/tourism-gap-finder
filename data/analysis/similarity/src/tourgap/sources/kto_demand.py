"""관광 수요 = 공백 우선순위 보정 전용.

'공급이 적다'와 '실제로 부족하다'를 구분하기 위한 데이터다(원칙 5).
쇼핑 시설이 적어도 관광객의 쇼핑 수요가 없다면 정책적 공백이라고 보기
어렵고, 체험 공급이 적은데 체험 수요가 높다면 강한 공백 후보다.

필요한 API (2026-08-17 기준 활용신청 대기 중):

* AreaTarResDemService/areaTarSvcDemList   지역별 관광 서비스 수요
* AreaTarResDemService/areaCulResDemList   지역별 문화 자원 수요

kto_performance와 같은 이유로 FIELD_MAP은 비워 두었다.
Swagger 확인 전에는 채우지 않는다.
"""

from __future__ import annotations

from typing import Protocol

import pandas as pd

from ..config import GAP_CATEGORIES
from ..provenance import Provenance, SourceRecord, SourceType

RESOURCE_DEMAND_BASE = "https://apis.data.go.kr/B551011/AreaTarResDemService"

#: 수요 API의 수요 항목을 우리 카테고리(lclsSystm1)로 잇는 표.
#: 실제 응답의 항목명을 확인한 뒤 채운다.
DEMAND_CATEGORY_MAP: dict[str, str] = {}

FIELD_MAP: dict[str, dict[str, str]] = {"service": {}, "culture": {}}


class DemandProvider(Protocol):
    def load(self, regions: pd.DataFrame, provenance: Provenance) -> pd.DataFrame:
        ...


class KtoDemandProvider:
    """실 API 어댑터. FIELD_MAP과 DEMAND_CATEGORY_MAP이 채워져야 동작한다."""

    def __init__(self, service_key: str) -> None:
        self._key = service_key

    def load(self, regions: pd.DataFrame, provenance: Provenance) -> pd.DataFrame:
        raise NotImplementedError(
            "AreaTarResDemService 활용신청 승인 후 Swagger로 응답 필드를 확인해 "
            "FIELD_MAP / DEMAND_CATEGORY_MAP을 채우고 구현하세요."
        )


class NeutralDemandProvider:
    """수요 데이터가 없을 때 쓰는 중립 제공자.

    가짜 수요 점수를 만들어 넣으면 공백 순위가 근거 없이 뒤바뀐다.
    그래서 값을 지어내지 않고 보정계수를 1.0으로 고정한다.
    즉 이 상태의 결과는 '공급 격차만 본 순위'이고, 리포트에도 그렇게 적는다.
    """

    def load(self, regions: pd.DataFrame, provenance: Provenance) -> pd.DataFrame:
        rows = [
            {
                "region_id": region_id,
                "category": category,
                "demand_percentile": pd.NA,
            }
            for region_id in regions["region_id"]
            for category in GAP_CATEGORIES
        ]
        provenance.add(
            SourceRecord(
                name="관광 자원 수요",
                source_type=SourceType.MOCK,
                endpoint="(AreaTarResDemService 활용신청 대기)",
                reference_period="해당 없음",
                note="미적용. 현재 공백 순위는 공급 격차만 반영",
                row_count=0,
            )
        )
        return pd.DataFrame(rows)
