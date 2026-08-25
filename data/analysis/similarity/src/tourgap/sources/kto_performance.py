"""관광 성과 지표 = benchmark 선정 전용.

원칙 3: 여기 들어가는 변수는 관광의 '결과'여야 한다.
원칙 1: 이 값은 유사성 계산에 절대 들어가지 않는다.

## 2026-08-17 API 확인 결과

활용신청은 모두 승인되어 403은 사라졌다. 다만 실제로 값을 주는 것은
DataLabService 하나뿐이다.

    DataLabService/locgoRegnVisitrDDList   ✅ 2023-01 ~ 2026-06 일별 데이터
    AreaTarDemDsService/areaTarSjrnDsList  ⚠ resultCode 0000이지만 totalCount 0
    AreaTarDemDsService/areaTarExpDsList   ⚠ 동일
    AreaTarResDemService/*                 ⚠ 동일
    AreaTarDivService/*                    ⚠ 동일

빈 응답은 파라미터 문제가 아니다. areaCd를 01~60·5자리로 전수 조회하고
baseYm을 2023-01 ~ 2026-06으로 훑어도 모두 0건이며, 정의되지 않은
파라미터는 INVALID_REQUEST_PARAMETER_ERROR로 분명히 거부된다
(수용되는 파라미터는 areaCd·signguCd·baseYm뿐). 즉 요청은 올바르고
아직 데이터가 공개되지 않은 상태로 판단된다.

그래서 성과 점수는 **방문자 데이터만으로** 구성한다. 체류·소비 강도가
열리면 config의 가중치에 추가하면 된다.
"""

from __future__ import annotations

import hashlib
from typing import Protocol

import pandas as pd

from ..config import REFERENCE_DIR
from ..provenance import Provenance, SourceRecord, SourceType
from .kto_datalab import FOREIGN, LOCAL, OUTSIDER, DataLabClient, month_range, to_frame

#: 성과 점수에 쓰는 지표. config.performance.weights의 키와 맞춘다.
PERFORMANCE_COLUMNS = [
    "stay_intensity",
    "consumption_intensity",
    "visitor_level",
    "visitor_yoy_growth",
    "outsider_ratio",
    "foreign_ratio",
]

#: 아직 데이터가 없는 지표 (전부 NaN으로 채워 점수에서 자동 제외된다)
UNAVAILABLE_COLUMNS = ["stay_intensity", "consumption_intensity"]

DATALAB_MAP_PATH = REFERENCE_DIR / "datalab_region_map.csv"

STAY_BASE = "https://apis.data.go.kr/B551011/AreaTarDemDsService"

#: 체류·소비 강도 API가 데이터를 공개하면 Swagger로 응답을 확인한 뒤 채운다.
#: 비어 있으면 KtoIntensityProvider가 거부한다. 필드명을 추측해 적지 않는다.
FIELD_MAP: dict[str, dict[str, str]] = {"stay": {}, "consumption": {}}


class PerformanceProvider(Protocol):
    def load(self, regions: pd.DataFrame, provenance: Provenance) -> pd.DataFrame:
        ...


class DataLabPerformanceProvider:
    """방문자 데이터 기반 관광 성과 (실데이터).

    만드는 지표:
      visitor_level       최근 12개월 외지인+외국인 방문자 합 (관광 유입 규모)
      visitor_yoy_growth  전년 동기 대비 증가율
      outsider_ratio      전체 방문자 중 외지인+외국인 비중
                          규모가 큰 도시가 무조건 유리해지는 것을 완화한다
      foreign_ratio       전체 방문자 중 외국인 비중
    """

    def __init__(
        self,
        client: DataLabClient,
        *,
        end_year: int = 2026,
        end_month: int = 6,
        months: int = 12,
    ) -> None:
        self._client = client
        self._end = (end_year, end_month)
        self._months = months

    def load(self, regions: pd.DataFrame, provenance: Provenance) -> pd.DataFrame:
        self._names: dict[str, str] = {}
        recent = self._window(*self._end, self._months)
        previous_end_year = self._end[0] - 1
        earlier = self._window(previous_end_year, self._end[1], self._months)

        mapping = _load_map()
        recent = _to_region(recent, regions, mapping, self._names)
        earlier = _to_region(earlier, regions, mapping, self._names)

        frame = regions[["region_id"]].merge(recent, on="region_id", how="left")
        frame = frame.merge(
            earlier[["region_id", "tourist_visitors"]].rename(
                columns={"tourist_visitors": "prior_visitors"}
            ),
            on="region_id",
            how="left",
        )

        frame["visitor_level"] = frame["tourist_visitors"]
        frame["visitor_yoy_growth"] = (
            frame["tourist_visitors"] - frame["prior_visitors"]
        ) / frame["prior_visitors"].replace(0, pd.NA)
        for column in UNAVAILABLE_COLUMNS:
            frame[column] = pd.NA

        start = f"{self._end[0] - 1}-{self._end[1] % 12 + 1:02d}"
        period = f"{start} ~ {self._end[0]}-{self._end[1]:02d}"
        provenance.add(
            SourceRecord(
                name="관광 성과 (방문자)",
                source_type=SourceType.REAL,
                endpoint="DataLabService /locgoRegnVisitrDDList",
                reference_period=period,
                note="이동통신 기반 '방문자'. 관광객 수와 동일하지 않은 proxy",
                row_count=int(frame["visitor_level"].notna().sum()),
            )
        )
        provenance.add(
            SourceRecord(
                name="관광 성과 (체류·소비 강도)",
                source_type=SourceType.MOCK,
                endpoint="AreaTarDemDsService (등록됨, 데이터 미공개)",
                reference_period="해당 없음",
                note="전 지역·전 기간 0건 응답. 공개되면 가중치에 추가",
                row_count=0,
            )
        )
        return frame[["region_id", *PERFORMANCE_COLUMNS]]

    def _window(self, year: int, month: int, count: int) -> pd.DataFrame:
        """기간 내 방문자를 지역×구분으로 합산한다."""
        frames = []
        for target_year, target_month in month_range(year, month, count):
            items = self._client.fetch_month(target_year, target_month)
            if items:
                frames.append(to_frame(items))
        if not frames:
            return pd.DataFrame(
                columns=["datalab_code", "tourist_visitors", "total_visitors"]
            )

        merged = pd.concat(frames, ignore_index=True)
        # 코드 -> 지역명. 통합으로 코드가 바뀐 지역을 이름으로 잇는 데 쓴다.
        self._names.update(
            dict(zip(merged["datalab_code"], merged["signguNm"], strict=True))
        )
        pivot = (
            merged.pivot_table(
                index="datalab_code",
                columns="tour_div",
                values="visitors",
                aggfunc="sum",
            )
            .fillna(0.0)
            .reset_index()
        )
        for division in (LOCAL, OUTSIDER, FOREIGN):
            if division not in pivot.columns:
                pivot[division] = 0.0
        # 현지인은 관광 성과가 아니다. 외지인 + 외국인만 관광 유입으로 센다.
        pivot["tourist_visitors"] = pivot[OUTSIDER] + pivot[FOREIGN]
        pivot["total_visitors"] = pivot[LOCAL] + pivot[OUTSIDER] + pivot[FOREIGN]
        pivot["foreign_visitors"] = pivot[FOREIGN]
        return pivot[
            [
                "datalab_code",
                "tourist_visitors",
                "total_visitors",
                "foreign_visitors",
            ]
        ]


def _load_map() -> pd.DataFrame:
    if not DATALAB_MAP_PATH.exists():
        return pd.DataFrame(columns=["datalab_code", "region_id", "weight"])
    return pd.read_csv(DATALAB_MAP_PATH, dtype={"datalab_code": str, "region_id": str})


#: DataLab은 과거 행정 코드, KTO 실제 자원은 새 법정동 코드 체계를 쓴다.
#: 광주광역시(29)와 전라남도(46)는 KTO 자원 데이터에서 prefix 12로 온다.
MERGED_PROVINCE_PREFIX = {"29": "12", "46": "12"}


def _to_region(
    frame: pd.DataFrame,
    regions: pd.DataFrame,
    mapping: pd.DataFrame,
    names: dict[str, str],
) -> pd.DataFrame:
    """DataLab 시군구 코드를 분석 기준 region_id로 옮긴다.

    DataLab은 개편 이전 코드를 쓴다(2026-08 기준).
      - 일반구를 따로 준다      -> 모 시로 합산 (41111 수원 장안구 -> 41110)
      - 광주(29)/전남(46) 분리  -> KTO prefix 12 안에서 지역명으로 매칭
      - 인천 개편 이전 구       -> datalab_region_map.csv 로 가중 배분

    지역명만으로 전국을 뒤지면 안 된다. '동구'는 부산·대구·인천 등 여러
    곳에 있어 엉뚱한 지역에 방문자가 붙는다. 그래서 이름 매칭은 반드시
    통합 대상 prefix(12) 안으로 범위를 좁혀서 한다.
    """
    from ..regions import parent_city_code

    known = set(regions["region_id"])
    # (새 시도 prefix, 지역명) -> region_id
    by_prefix_name = {
        (region_id[:2], name): region_id
        for region_id, name in zip(
            regions["region_id"], regions["region_name"], strict=True
        )
    }
    override = {
        code: group[["region_id", "weight"]].values.tolist()
        for code, group in mapping.groupby("datalab_code")
    }

    rows = []
    for record in frame.itertuples():
        code = record.datalab_code

        if code in override:
            for region_id, weight in override[code]:
                rows.append(_scaled(record, region_id, float(weight)))
            continue

        target = code if code in known else parent_city_code(code)
        if target not in known:
            new_prefix = MERGED_PROVINCE_PREFIX.get(code[:2])
            name = names.get(code)
            if new_prefix and name:
                target = by_prefix_name.get((new_prefix, name), "")
        if target in known:
            rows.append(_scaled(record, target, 1.0))

    if not rows:
        return pd.DataFrame(columns=["region_id", "tourist_visitors", "total_visitors"])
    return (
        pd.DataFrame(rows)
        .groupby("region_id", as_index=False)
        .sum(numeric_only=True)
        .assign(
            outsider_ratio=lambda f: f["tourist_visitors"]
            / f["total_visitors"].replace(0, pd.NA),
            foreign_ratio=lambda f: f["foreign_visitors"]
            / f["total_visitors"].replace(0, pd.NA),
        )
    )


def _scaled(record, region_id: str, weight: float) -> dict:
    return {
        "region_id": region_id,
        "tourist_visitors": record.tourist_visitors * weight,
        "total_visitors": record.total_visitors * weight,
        "foreign_visitors": record.foreign_visitors * weight,
    }


class KtoIntensityProvider:
    """체류·소비 강도 어댑터. 데이터가 공개되고 FIELD_MAP이 채워져야 동작한다."""

    def __init__(self, service_key: str) -> None:
        self._key = service_key

    def load(self, regions: pd.DataFrame, provenance: Provenance) -> pd.DataFrame:
        raise NotImplementedError(
            "AreaTarDemDsService가 아직 데이터를 반환하지 않습니다. "
            "공개된 뒤 Swagger로 응답 필드를 확인해 FIELD_MAP을 채우세요. "
            "필드명을 추측해서 적지 마세요."
        )


class MockPerformanceProvider:
    """모든 성과 API가 막혔을 때 쓰는 자리 채우기. 값은 아무 의미가 없다."""

    def load(self, regions: pd.DataFrame, provenance: Provenance) -> pd.DataFrame:
        rows = []
        for region_id in regions["region_id"]:
            rows.append(
                {
                    "region_id": region_id,
                    "stay_intensity": round(20 + 60 * _unit_hash(region_id, "stay"), 2),
                    "consumption_intensity": round(
                        20 + 60 * _unit_hash(region_id, "exp"), 2
                    ),
                    "visitor_level": round(
                        1_000_000 * (0.2 + 4 * _unit_hash(region_id, "vis"))
                    ),
                    "visitor_yoy_growth": round(
                        -0.12 + 0.30 * _unit_hash(region_id, "growth"), 4
                    ),
                    "outsider_ratio": round(
                        0.3 + 0.5 * _unit_hash(region_id, "out"), 4
                    ),
                    "foreign_ratio": round(
                        0.01 + 0.1 * _unit_hash(region_id, "for"), 4
                    ),
                }
            )
        provenance.add(
            SourceRecord(
                name="관광 성과 (전체)",
                source_type=SourceType.MOCK,
                endpoint="(성과 API 미가용)",
                reference_period="해당 없음",
                note="값 자체가 가짜. 정책 판단에 쓰면 안 됨",
                row_count=len(rows),
            )
        )
        return pd.DataFrame(rows)


def _unit_hash(*parts: str) -> float:
    digest = hashlib.sha256("|".join(parts).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64
