"""유사성 전용 구조 변수.

원칙 1을 지키기 위해, 여기서 만드는 변수에는 관광 콘텐츠 공급이나
관광 성과가 절대 들어가면 안 된다. TourAPI에서 가져오는 것은 자원의
'좌표'뿐이고, 그것도 지역 중심점을 잡아 접근성을 계산하는 용도로만 쓴다.
개수·유형은 쓰지 않는다.

제공자는 두 가지다.

* SgisStructuralProvider    SGIS 총조사 주요지표 + 행정구역경계 (real)
* MockStructuralProvider    SGIS 키가 없을 때 쓰는 자리 채우기 (mock)

둘 다 같은 컬럼을 돌려주므로 아래 단계는 어느 쪽인지 몰라도 된다.
"""

from __future__ import annotations

import hashlib
import math
from typing import Protocol

import pandas as pd

from ..config import REFERENCE_DIR, SIMILARITY_FEATURES, get_config
from ..provenance import Provenance, SourceRecord, SourceType
from .sgis import SgisClient, geometry_area_m2
from .urbanization import DEFAULT_URBAN_BOUNDARY, load_urban_area_by_sgis_code

STRUCTURAL_COLUMNS = [
    "area_km2",
    "total_population",
    "population_density",
    "average_age",
    "urbanization_ratio",
    "coastal_dummy",
    "island_ratio",
    "forest_ratio",
    "farmland_ratio",
    "terrain_relief",
    "annual_mean_temperature",
    "annual_temperature_range",
    "annual_precipitation",
    "business_density",
    "manufacturing_worker_ratio",
    "construction_logistics_worker_ratio",
    "knowledge_public_service_worker_ratio",
]

COMPATIBILITY_COLUMNS = [
    "population",
    "density",
    "avg_household_size",
    "farm_household_ratio",
    "forestry_household_ratio",
    "fishery_household_ratio",
]

COASTAL_PATH = REFERENCE_DIR / "coastal_island.csv"


class StructuralProvider(Protocol):
    def load(self, regions: pd.DataFrame, provenance: Provenance) -> pd.DataFrame:
        ...


# ---------------------------------------------------------------------------
# 공통: 중심점과 접근성 (TourAPI 좌표에서 실제로 계산한다)
# ---------------------------------------------------------------------------
def region_centroids(resources: pd.DataFrame) -> pd.DataFrame:
    """지역별 관광자원 좌표의 중앙값을 지역 중심점으로 쓴다.

    행정경계 중심점이 아니므로 proxy다. 다만 평균 대신 중앙값을 써서
    섬·산간의 외딴 좌표에 끌려가지 않게 한다. SGIS 경계를 받을 수 있으면
    그쪽 중심점으로 대체된다.
    """
    valid = resources[
        resources["longitude"].notna()
        & resources["latitude"].notna()
        & (resources["region_id"] != "")
    ]
    grouped = valid.groupby("region_id").agg(
        centroid_lon=("longitude", "median"),
        centroid_lat=("latitude", "median"),
    )
    return grouped.reset_index()


def haversine_km(lon1: float, lat1: float, lon2: float, lat2: float) -> float:
    radius = 6371.0088
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = phi2 - phi1
    d_lambda = math.radians(lon2 - lon1)
    a = (
        math.sin(d_phi / 2) ** 2
        + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    )
    return 2 * radius * math.asin(math.sqrt(a))


def metro_distance_km(frame: pd.DataFrame) -> pd.Series:
    """가장 가까운 대도시까지의 직선거리.

    자동차 이동시간이 이상적이지만 MVP에서는 직선거리로 대신한다(proxy).
    Kakao Mobility를 붙이면 이 컬럼만 갈아 끼우면 된다.
    """
    cities = get_config().gateway_cities

    def nearest(row) -> float:
        if pd.isna(row.centroid_lon) or pd.isna(row.centroid_lat):
            return float("nan")
        return min(
            haversine_km(row.centroid_lon, row.centroid_lat, lon, lat)
            for lon, lat in cities.values()
        )

    return frame.apply(nearest, axis=1)


def load_coastal_flags(regions: pd.DataFrame) -> pd.DataFrame:
    """해안/도서 여부. 정적 참조 테이블."""
    if not COASTAL_PATH.exists():
        return pd.DataFrame(
            {
                "region_id": regions["region_id"],
                "coastal_flag": 0,
                "island_flag": 0,
                "coastal_dummy": 0,
                "island_ratio": 0.0,
            }
        )
    table = pd.read_csv(COASTAL_PATH, dtype={"region_id": str})
    merged = regions[["region_id"]].merge(table, on="region_id", how="left")
    merged["coastal_flag"] = merged["coastal_flag"].fillna(0).astype(int)
    merged["island_flag"] = merged["island_flag"].fillna(0).astype(int)
    merged["coastal_dummy"] = merged["coastal_flag"]
    merged["island_ratio"] = merged["island_flag"].astype(float)
    merged["coastal_dummy_source_type"] = SourceType.STATIC_REFERENCE.value
    merged["island_ratio_source_type"] = SourceType.STATIC_REFERENCE.value
    return merged[
        [
            "region_id",
            "coastal_flag",
            "island_flag",
            "coastal_dummy",
            "island_ratio",
            "coastal_dummy_source_type",
            "island_ratio_source_type",
        ]
    ]


# ---------------------------------------------------------------------------
# SGIS (real)
# ---------------------------------------------------------------------------
#: SGIS 시도명 -> 우리 지역 마스터의 시도명 후보.
#: SGIS 2020년 자료는 2020년 행정구역 기준이라 이름이 다른 곳이 있다.
PROVINCE_ALIASES: dict[str, list[str]] = {
    "강원특별자치도": ["강원특별자치도", "강원도"],
    "전북특별자치도": ["전북특별자치도", "전라북도"],
}

SGIS_MAP_PATH = REFERENCE_DIR / "sgis_region_map.csv"

#: 같은 시도를 가리키는 표기를 하나로 모은다. SGIS의 인구 API와 경계 API가
#: 서로 다른 시점의 시도명을 쓰기 때문이다(경계는 '강원도', 인구는
#: '강원특별자치도').
_PROVINCE_KEYS = {
    "강원도": "강원",
    "강원특별자치도": "강원",
    "전라북도": "전북",
    "전북특별자치도": "전북",
    "제주도": "제주",
    "제주특별자치도": "제주",
    "세종특별자치시": "세종",
    "세종시": "세종",
}


def canonical_province(name: str) -> str:
    text = str(name).strip()
    return _PROVINCE_KEYS.get(text, text)


_SUM_COLUMNS = [
    "population",
    "total_household",
    "farm_household",
    "forestry_household",
    "fishery_household",
]

_AREA_SUM_COLUMNS = ["urban_area_km2"]

_INDUSTRY_SUM_COLUMNS = [
    "total_business_count",
    "eligible_worker_count",
    "manufacturing_worker_count",
    "construction_logistics_worker_count",
    "knowledge_public_service_worker_count",
]


class SgisStructuralProvider:
    """통계청 SGIS 총조사 주요지표 + 행정구역경계.

    주의: SGIS의 adm_cd는 법정동 코드가 아니라 통계청 자체 코드다
    (부산 = 21, 법정동은 26). 그래서 코드로 조인하지 않고
    (시도명, 시군구명)으로 맞춘 뒤, 안 맞는 곳만
    data/reference/sgis_region_map.csv 로 보정한다.

    SGIS는 일반구를 '청주시 흥덕구'처럼 한 행으로 주므로 이름 앞부분으로
    모 시를 알아내 합산한다.
    """

    def __init__(
        self,
        client: SgisClient,
        year: str | None = None,
        company_year: str | None = None,
    ) -> None:
        self._client = client
        self._year = year or get_config().sgis_year
        self._company_year = company_year or get_config().sgis_company_year

    def load(self, regions: pd.DataFrame, provenance: Provenance) -> pd.DataFrame:
        sgis = self._municipality_frame()
        overrides = _load_overrides()
        frame = _join_by_name(regions, sgis, overrides)

        frame["density"] = frame["population"] / frame["area_km2"]
        frame["total_population"] = frame["population"]
        frame["population_density"] = frame["density"]
        frame["urbanization_ratio"] = frame["urban_area_km2"] / frame["area_km2"]
        frame.loc[
            ~frame["urbanization_ratio"].between(0, 1), "urbanization_ratio"
        ] = float("nan")
        frame["business_density"] = frame["total_business_count"] / frame["area_km2"]
        frame["manufacturing_worker_ratio"] = (
            frame["manufacturing_worker_count"] / frame["eligible_worker_count"]
        )
        frame["construction_logistics_worker_ratio"] = (
            frame["construction_logistics_worker_count"]
            / frame["eligible_worker_count"]
        )
        frame["knowledge_public_service_worker_ratio"] = (
            frame["knowledge_public_service_worker_count"]
            / frame["eligible_worker_count"]
        )
        frame["avg_household_size"] = frame["population"] / frame["total_household"]
        for name, column in [
            ("farm_household_ratio", "farm_household"),
            ("forestry_household_ratio", "forestry_household"),
            ("fishery_household_ratio", "fishery_household"),
        ]:
            frame[name] = frame[column] / frame["total_household"]

        matched = int(frame["population"].notna().sum())
        provenance.add(
            SourceRecord(
                name="지역 구조 변수 (인구·가구·농림어가)",
                source_type=SourceType.REAL,
                endpoint="SGIS /stats/population.json",
                reference_period=f"{self._year}년 인구주택총조사",
                note=(
                    f"{matched}/{len(regions)}개 지역 매칭. " "인천 4개 구는 2026년 개편분이라 추정 배분"
                ),
                row_count=matched,
            )
        )
        industry_features = [
            "business_density",
            "manufacturing_worker_ratio",
            "construction_logistics_worker_ratio",
            "knowledge_public_service_worker_ratio",
        ]
        industry_matched = int(frame[industry_features].notna().all(axis=1).sum())
        provenance.add(
            SourceRecord(
                name="사업체·산업별 종사자 구조",
                source_type=SourceType.REAL,
                endpoint="SGIS /stats/company.json",
                reference_period=f"{self._company_year}년 전국사업체조사",
                note=(
                    "사업체 밀도는 전체 사업체 수/면적. 종사자 비율 분모에서 "
                    "관광 결과와 가까운 I(숙박·음식), R(예술·스포츠·여가) 제외"
                ),
                row_count=industry_matched,
            )
        )
        if DEFAULT_URBAN_BOUNDARY.exists():
            urban_matched = int(frame["urbanization_ratio"].notna().sum())
            provenance.add(
                SourceRecord(
                    name="도시화율",
                    source_type=SourceType.STATIC_REFERENCE,
                    endpoint="data/raw/urbanization/BND_UA_PG.zip",
                    reference_period="2024-06-30 SGIS 도시화지역 경계",
                    note="시군구별 UA_AREA 합계 / SGIS 행정구역 면적. 일반구는 모 시로 합산",
                    row_count=urban_matched,
                )
            )
        provenance.add(
            SourceRecord(
                name="면적",
                source_type=SourceType.REAL,
                endpoint="SGIS /boundary/hadmarea.geojson",
                reference_period=f"{self._year}년 경계",
                note="shoelace 공식으로 계산 (EPSG:5179, m)",
                row_count=int(frame["area_km2"].notna().sum()),
            )
        )
        for column in [
            "area_km2",
            "total_population",
            "population_density",
            "average_age",
        ]:
            frame[f"{column}_source_type"] = SourceType.REAL.value
        if frame["urbanization_ratio"].notna().any():
            frame["urbanization_ratio_source_type"] = SourceType.STATIC_REFERENCE.value
        for column in industry_features:
            if frame[column].notna().any():
                frame[f"{column}_source_type"] = SourceType.REAL.value
        available_structural = {
            "area_km2",
            "total_population",
            "population_density",
            "average_age",
        }
        if frame["urbanization_ratio"].notna().any():
            available_structural.add("urbanization_ratio")
        available_structural.update(
            column for column in industry_features if frame[column].notna().any()
        )
        _mark_unavailable_features(
            frame,
            [c for c in SIMILARITY_FEATURES if c not in available_structural],
            "required official source file or API adapter is not configured",
        )
        columns = [
            "region_id",
            *STRUCTURAL_COLUMNS,
            *COMPATIBILITY_COLUMNS,
            *[
                f"{c}_source_type"
                for c in STRUCTURAL_COLUMNS
                if f"{c}_source_type" in frame
            ],
            *[
                f"{c}_missing_reason"
                for c in STRUCTURAL_COLUMNS
                if f"{c}_missing_reason" in frame
            ],
        ]
        return frame[columns]

    def _municipality_frame(self) -> pd.DataFrame:
        """SGIS 시군구 단위 표. 일반구는 모 시로 합쳐서 돌려준다."""
        rows: list[dict] = []

        for province in self._client.fetch_population(year=self._year, low_search="1"):
            province_code = str(province.get("adm_cd", ""))
            province_name = str(province.get("adm_nm", ""))
            for record in self._client.fetch_population(
                year=self._year, adm_cd=province_code, low_search="1"
            ):
                name = str(record.get("adm_nm", ""))
                rows.append(
                    {
                        "sgis_province": province_name,
                        # '청주시 흥덕구' -> '청주시'
                        "sgis_municipality": name.split()[0],
                        "sgis_adm_cd": str(record.get("adm_cd", "")),
                        "population": _number(record.get("tot_ppltn")),
                        "average_age": _number(record.get("avg_age")),
                        "total_household": _number(record.get("tot_family")),
                        "farm_household": _number(record.get("nongga_cnt")),
                        "forestry_household": _number(record.get("imga_cnt")),
                        "fishery_household": _number(record.get("naesuoga_cnt"))
                        + _number(record.get("haesuoga_cnt")),
                    }
                )

        frame = pd.DataFrame(rows)
        urban = load_urban_area_by_sgis_code()
        if urban is None:
            frame["urban_area_km2"] = float("nan")
        else:
            frame = frame.merge(urban, on="sgis_adm_cd", how="left")
            # 이 파일은 전국 도시화지역 경계 전수 자료다. 지역 코드가
            # 파일에 없다는 것은 결측이 아니라 기준을 충족하는 도시화지역
            # 폴리곤이 하나도 없다는 뜻이므로 이 경우에만 0으로 둔다.
            frame["urban_area_km2"] = frame["urban_area_km2"].fillna(0.0)
        grouped = frame.groupby(["sgis_province", "sgis_municipality"])

        aggregated = grouped[[*_SUM_COLUMNS, *_AREA_SUM_COLUMNS]].sum(min_count=1)
        # 평균연령은 더하면 안 되므로 인구 가중평균한다.
        weighted = grouped.apply(
            lambda g: (
                (g["average_age"] * g["population"]).sum() / g["population"].sum()
                if g["population"].sum()
                else float("nan")
            ),
            include_groups=False,
        )
        aggregated["average_age"] = weighted
        aggregated = aggregated.reset_index()
        aggregated["_province_key"] = aggregated["sgis_province"].map(
            canonical_province
        )
        industry = self._industry_frame()
        aggregated = aggregated.merge(
            industry,
            on=["_province_key", "sgis_municipality"],
            how="left",
        )

        areas = self._area_frame()
        merged = aggregated.merge(
            areas,
            on=["_province_key", "sgis_municipality"],
            how="left",
        )

        # 시도가 바뀐 지역(2023년 군위군: 경북 -> 대구)은 시도 기준으로는
        # 못 찾는다. 지역명이 전국에서 유일하면 그 값으로 채운다.
        unique = areas["sgis_municipality"].value_counts()
        unique_areas = areas[
            areas["sgis_municipality"].isin(unique[unique == 1].index)
        ].set_index("sgis_municipality")["area_km2"]
        fallback = merged["sgis_municipality"].map(unique_areas)
        merged["area_km2"] = merged["area_km2"].fillna(fallback)

        return merged.drop(columns=["_province_key"])

    def _industry_frame(self) -> pd.DataFrame:
        """최신 사업체조사를 시군구 단위 산업 구조로 집계한다."""
        config = get_config()
        group_codes = {
            "manufacturing_worker_count": config.industry_groups["manufacturing"],
            "construction_logistics_worker_count": config.industry_groups[
                "construction_logistics"
            ],
            "knowledge_public_service_worker_count": config.industry_groups[
                "knowledge_public_service"
            ],
        }
        requested_codes = {
            *config.excluded_industries,
            *(code for codes in group_codes.values() for code in codes),
        }
        official_codes = {
            str(record.get("class_code", ""))
            for record in self._client.fetch_industry_codes(
                class_deg=config.sgis_industry_class_deg
            )
        }
        missing_codes = requested_codes - official_codes
        if missing_codes:
            raise ValueError(
                "SGIS 제11차 산업분류에 필요한 대분류 코드가 없습니다: " f"{sorted(missing_codes)}"
            )
        rows: list[dict[str, object]] = []

        provinces = self._client.fetch_company(year=self._company_year, low_search="1")
        for province in provinces:
            province_code = str(province.get("adm_cd", ""))
            province_name = str(province.get("adm_nm", ""))
            totals = self._client.fetch_company(
                year=self._company_year,
                adm_cd=province_code,
                low_search="1",
            )
            by_municipality: dict[str, dict[str, object]] = {}
            for record in totals:
                name = str(record.get("adm_nm", "")).split()[0]
                by_municipality[name] = {
                    "_province_key": canonical_province(province_name),
                    "sgis_municipality": name,
                    "total_business_count": _number(record.get("corp_cnt")),
                    "total_worker_count": _number(record.get("tot_worker")),
                }

            for code in sorted(requested_codes):
                records = self._client.fetch_company(
                    year=self._company_year,
                    adm_cd=province_code,
                    class_code=code,
                    low_search="1",
                )
                for record in records:
                    name = str(record.get("adm_nm", "")).split()[0]
                    if name not in by_municipality:
                        continue
                    by_municipality[name][f"worker_{code}"] = _number(
                        record.get("tot_worker")
                    )

            for record in by_municipality.values():
                total_workers = float(record.pop("total_worker_count"))
                excluded_workers = sum(
                    float(record.get(f"worker_{code}", 0.0))
                    for code in config.excluded_industries
                )
                record["eligible_worker_count"] = total_workers - excluded_workers
                for column, codes in group_codes.items():
                    record[column] = sum(
                        float(record.get(f"worker_{code}", 0.0)) for code in codes
                    )
                rows.append(record)

        frame = pd.DataFrame(rows)
        if frame.empty:
            return pd.DataFrame(
                columns=["_province_key", "sgis_municipality", *_INDUSTRY_SUM_COLUMNS]
            )
        return (
            frame.groupby(["_province_key", "sgis_municipality"])[_INDUSTRY_SUM_COLUMNS]
            .sum(min_count=1)
            .reset_index()
        )

    def _area_frame(self) -> pd.DataFrame:
        """SGIS 경계에서 시군구 면적(km2).

        코드로 잇지 않는다. 인구 API와 경계 API가 군 지역에 서로 다른
        코드를 쓴다(경북 청도군: 인구 37560, 경계 37340). 두 응답 모두
        전체 지역명을 주므로 이름으로 맞춘다.
        """
        rows: list[dict] = []
        for province in self._client.fetch_population(year=self._year, low_search="1"):
            payload = self._client.fetch_boundary(
                year=self._year,
                adm_cd=str(province.get("adm_cd", "")),
                low_search="1",
            )
            for feature in payload.get("features", []):
                properties = feature.get("properties") or {}
                # '경상북도 포항시 남구' -> ('경상북도', '포항시')
                tokens = str(properties.get("adm_nm", "")).split()
                if len(tokens) < 2:
                    continue
                rows.append(
                    {
                        "_province_key": canonical_province(tokens[0]),
                        "sgis_municipality": tokens[1],
                        "area_km2": geometry_area_m2(feature.get("geometry") or {})
                        / 1_000_000,
                    }
                )

        frame = pd.DataFrame(rows)
        return (
            frame.groupby(["_province_key", "sgis_municipality"])["area_km2"]
            .sum()
            .reset_index()
        )


def _load_overrides() -> pd.DataFrame:
    if not SGIS_MAP_PATH.exists():
        return pd.DataFrame(
            columns=[
                "region_id",
                "sgis_province",
                "sgis_municipality",
                "weight",
            ]
        )
    return pd.read_csv(SGIS_MAP_PATH, dtype={"region_id": str})


def _join_by_name(
    regions: pd.DataFrame, sgis: pd.DataFrame, overrides: pd.DataFrame
) -> pd.DataFrame:
    """(시도명, 시군구명)으로 SGIS 값을 붙인다."""
    lookup = sgis.set_index(["sgis_province", "sgis_municipality"])
    override_ids = set(overrides["region_id"])
    value_columns = [
        *_SUM_COLUMNS,
        *_AREA_SUM_COLUMNS,
        *_INDUSTRY_SUM_COLUMNS,
        "area_km2",
        "average_age",
    ]

    rows = []
    for region in regions.itertuples():
        if region.region_id in override_ids:
            rows.append(
                _combine_override(
                    region.region_id,
                    overrides[overrides["region_id"] == region.region_id],
                    lookup,
                    value_columns,
                )
            )
            continue

        candidates = PROVINCE_ALIASES.get(region.province_name, [region.province_name])
        record = {"region_id": region.region_id}
        for province in candidates:
            key = (province, region.region_name)
            if key in lookup.index:
                matched = lookup.loc[key]
                record.update({column: matched[column] for column in value_columns})
                break
        else:
            record.update({column: float("nan") for column in value_columns})
        rows.append(record)

    return pd.DataFrame(rows)


def _combine_override(
    region_id: str,
    mapping: pd.DataFrame,
    lookup: pd.DataFrame,
    value_columns: list[str],
) -> dict:
    """여러 SGIS 지역을 가중 합산해 한 지역을 만든다.

    2026년 인천 행정구역 개편처럼 2020년 통계에 대응 지역이 없을 때 쓴다.
    합계형은 weight를 곱해 더하고, 평균연령은 인구 가중평균한다.
    """
    record: dict[str, float | str] = {"region_id": region_id}
    totals = dict.fromkeys(
        [*_SUM_COLUMNS, *_AREA_SUM_COLUMNS, *_INDUSTRY_SUM_COLUMNS, "area_km2"],
        0.0,
    )
    age_numerator = 0.0
    age_denominator = 0.0
    found = False

    for row in mapping.itertuples():
        key = (row.sgis_province, row.sgis_municipality)
        if key not in lookup.index:
            continue
        found = True
        source = lookup.loc[key]
        weight = float(row.weight)
        for column in totals:
            totals[column] += float(source[column] or 0.0) * weight
        population = float(source["population"] or 0.0) * weight
        age_numerator += float(source["average_age"] or 0.0) * population
        age_denominator += population

    if not found:
        record.update({column: float("nan") for column in value_columns})
        return record

    record.update(totals)
    record["average_age"] = (
        age_numerator / age_denominator if age_denominator else float("nan")
    )
    return record


def _number(value: object) -> float:
    """SGIS는 값이 없을 때 'N/A' 문자열을 준다."""
    text = str(value).strip()
    if not text or text.upper() in {"N/A", "NA", "NONE", "NAN"}:
        return 0.0
    try:
        result = float(text)
    except (TypeError, ValueError):
        return 0.0
    return 0.0 if math.isnan(result) else result


# ---------------------------------------------------------------------------
# Mock (SGIS 키가 없을 때)
# ---------------------------------------------------------------------------
class MockStructuralProvider:
    """SGIS 키가 없을 때 파이프라인을 돌리기 위한 가짜 구조 변수.

    값 자체는 가짜지만 region_id 해시로 결정론적으로 만들어 실행할 때마다
    같은 결과가 나오게 한다. 또 자치구/시/군의 전형적인 규모대를 반영해
    peer 결과가 최소한 구조적으로는 말이 되게 한다.

    **이 값으로 나온 유사지역을 실제 정책 판단에 쓰면 안 된다.**
    SGIS 키를 넣으면 SgisStructuralProvider로 자동 교체된다.
    """

    # (인구 하한, 인구 상한, 면적 하한, 면적 상한)
    PROFILES = {
        "자치구": (90_000, 600_000, 10.0, 60.0),
        "시": (80_000, 1_100_000, 90.0, 1_400.0),
        "군": (18_000, 110_000, 300.0, 1_800.0),
        "특별자치시": (380_000, 400_000, 460.0, 470.0),
        "기타": (50_000, 300_000, 100.0, 600.0),
    }

    def load(self, regions: pd.DataFrame, provenance: Provenance) -> pd.DataFrame:
        rows = []
        for region in regions.itertuples():
            low_pop, high_pop, low_area, high_area = self.PROFILES.get(
                region.admin_type, self.PROFILES["기타"]
            )
            r1 = _unit_hash(region.region_id, "pop")
            r2 = _unit_hash(region.region_id, "area")
            r3 = _unit_hash(region.region_id, "age")
            r4 = _unit_hash(region.region_id, "hh")

            population = low_pop + r1 * (high_pop - low_pop)
            area = low_area + r2 * (high_area - low_area)
            is_rural = region.admin_type == "군"
            rows.append(
                {
                    "region_id": region.region_id,
                    "total_population": round(population),
                    "area_km2": round(area, 2),
                    "population_density": round(population / area, 2),
                    "average_age": round((48.0 if is_rural else 41.0) + r3 * 6.0, 1),
                    "avg_household_size": round(2.0 + r4 * 0.6, 2),
                    "farm_household_ratio": round(
                        (0.18 if is_rural else 0.01) * (0.4 + r1), 4
                    ),
                    "forestry_household_ratio": round(
                        (0.05 if is_rural else 0.002) * (0.4 + r2), 4
                    ),
                    "fishery_household_ratio": round(
                        (0.04 if is_rural else 0.003) * (0.4 + r3), 4
                    ),
                    "urbanization_ratio": round(
                        (0.18 if is_rural else 0.68)
                        + _unit_hash(region.region_id, "urban") * 0.20,
                        4,
                    ),
                    "coastal_dummy": 0,
                    "island_ratio": 0.0,
                    "forest_ratio": round(
                        (0.45 if is_rural else 0.18)
                        + _unit_hash(region.region_id, "forest") * 0.20,
                        4,
                    ),
                    "farmland_ratio": round(
                        (0.28 if is_rural else 0.04)
                        + _unit_hash(region.region_id, "farm") * 0.15,
                        4,
                    ),
                    "terrain_relief": round(
                        (320 if is_rural else 90)
                        + _unit_hash(region.region_id, "relief") * 500,
                        1,
                    ),
                    "annual_mean_temperature": round(
                        9.0 + _unit_hash(region.region_id, "temp") * 7.5, 2
                    ),
                    "annual_temperature_range": round(
                        20.0 + _unit_hash(region.region_id, "range") * 12.0, 2
                    ),
                    "annual_precipitation": round(
                        900 + _unit_hash(region.region_id, "precip") * 900, 1
                    ),
                    "business_density": round(
                        (population / area)
                        * (0.06 + _unit_hash(region.region_id, "biz") * 0.08),
                        3,
                    ),
                    "manufacturing_worker_ratio": round(
                        _unit_hash(region.region_id, "mfg") * 0.35, 4
                    ),
                    "construction_logistics_worker_ratio": round(
                        0.05 + _unit_hash(region.region_id, "logistics") * 0.25,
                        4,
                    ),
                    "knowledge_public_service_worker_ratio": round(
                        0.12 + _unit_hash(region.region_id, "knowledge") * 0.45,
                        4,
                    ),
                }
            )

        frame = pd.DataFrame(rows)
        frame["population"] = frame["total_population"]
        frame["density"] = frame["population_density"]
        for column in STRUCTURAL_COLUMNS:
            frame[f"{column}_source_type"] = SourceType.MOCK.value
        provenance.add(
            SourceRecord(
                name="지역 구조 변수 (인구·면적·가구)",
                source_type=SourceType.MOCK,
                endpoint="(SGIS 키 미발급 — 합성값)",
                reference_period="해당 없음",
                note="SGIS_CONSUMER_KEY/SECRET을 .env에 넣으면 실데이터로 교체",
                row_count=len(rows),
            )
        )
        return frame


def _unit_hash(*parts: str) -> float:
    """문자열 -> [0, 1) 결정론적 실수."""
    digest = hashlib.sha256("|".join(parts).encode()).digest()
    return int.from_bytes(digest[:8], "big") / 2**64


def _mark_unavailable_features(
    frame: pd.DataFrame, columns: list[str], reason: str
) -> None:
    for column in columns:
        if column not in frame.columns:
            frame[column] = float("nan")
        frame[f"{column}_missing_reason"] = reason
