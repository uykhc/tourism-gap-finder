"""아직 연결되지 않은 엔드포인트의 고정 예시와 구조 응답 메타데이터.

여기 있는 숫자는 **화면 개발용 표본**이며 정책 판단에 쓰면 안 된다.

고정 숫자를 응답하는 엔드포인트는 성과와 비교 두 개뿐이다. 구조 특성 응답은
이 모듈의 라벨·그룹·가중치·출처 형식만 재사용하고, 실제 값과 대상 지역은
``region_features.csv``의 전국 스냅숏으로 교체한다.

===================================  ==========================
엔드포인트                            필요한 키
===================================  ==========================
``GET /regions/{id}/performance``     VISITOR
``GET /compare``                      TourAPI + VISITOR
===================================  ==========================

``/regions``·``/provinces``는 ``services.regions``의 전국 표를 읽고,
``/peers``·``/gaps``·``/report``는 ``services.artifacts``의 분석 산출물을 읽는다.
"""

from __future__ import annotations

from typing import Any

EXAMPLE_NOTICE = (
    "화면 개발용 예시 응답입니다. 실제 분석 결과가 아니며 정책 판단에 쓰지 않습니다."
)

# ---------------------------------------------------------------------------
# 지역 마스터 — contracts/hankkeut_contracts/data/regions.csv 의 실제 행 일부
# ---------------------------------------------------------------------------
_GANGWON: list[tuple[str, str, str]] = [
    ("51110", "춘천시", "시"), ("51130", "원주시", "시"), ("51150", "강릉시", "시"),
    ("51170", "동해시", "시"), ("51190", "태백시", "시"), ("51210", "속초시", "시"),
    ("51230", "삼척시", "시"), ("51720", "홍천군", "군"), ("51730", "횡성군", "군"),
    ("51750", "영월군", "군"), ("51760", "평창군", "군"), ("51770", "정선군", "군"),
    ("51780", "철원군", "군"), ("51790", "화천군", "군"), ("51800", "양구군", "군"),
    ("51810", "인제군", "군"), ("51820", "고성군", "군"), ("51830", "양양군", "군"),
]

REGIONS: list[dict[str, Any]] = [
    {"region_id": "47130", "province_name": "경상북도", "region_name": "경주시", "administrative_type": "시"},
    {"region_id": "47110", "province_name": "경상북도", "region_name": "포항시", "administrative_type": "시"},
    {"region_id": "44210", "province_name": "충청남도", "region_name": "서산시", "administrative_type": "시"},
    {"region_id": "44270", "province_name": "충청남도", "region_name": "당진시", "administrative_type": "시"},
    {"region_id": "52130", "province_name": "전북특별자치도", "region_name": "군산시", "administrative_type": "시"},
    {"region_id": "12150", "province_name": "전라남도", "region_name": "순천시", "administrative_type": "시"},
    {"region_id": "12130", "province_name": "전라남도", "region_name": "여수시", "administrative_type": "시"},
    {"region_id": "12190", "province_name": "전라남도", "region_name": "광양시", "administrative_type": "시"},
    {"region_id": "11680", "province_name": "서울특별시", "region_name": "강남구", "administrative_type": "자치구"},
    {"region_id": "47940", "province_name": "경상북도", "region_name": "울릉군", "administrative_type": "군"},
    *(
        {
            "region_id": region_id,
            "province_name": "강원특별자치도",
            "region_name": name,
            "administrative_type": admin_type,
        }
        for region_id, name, admin_type in _GANGWON
    ),
]

REGION_DETAIL: dict[str, Any] = {
    **REGIONS[0],
    "area_km2": 1324.39,
    "total_population": 248326,
    "coastal": True,
}


# ---------------------------------------------------------------------------
# 구조 특성 17개 — tourgap.config.SIMILARITY_FEATURES / FEATURE_GROUPS
# ---------------------------------------------------------------------------
GROUP_WEIGHTS: dict[str, float] = {
    "regional_scale": 0.10,
    "urban_concentration": 0.10,
    "population_structure": 0.10,
    "natural_geography": 0.30,
    "climate": 0.15,
    "industry_structure": 0.25,
}

_FEATURES: list[tuple[str, str, str, float | None, str]] = [
    # (feature, 한국어 라벨, 요인 그룹, 값, 출처 유형)
    ("area_km2", "면적", "regional_scale", 1324.39, "real"),
    ("total_population", "총인구", "regional_scale", 248326.0, "real"),
    ("population_density", "인구밀도", "urban_concentration", 187.5, "real"),
    ("urbanization_ratio", "도시화율", "urban_concentration", 0.0721, "real"),
    ("business_density", "사업체 밀도", "urban_concentration", 14.62, "real"),
    ("average_age", "평균연령", "population_structure", 45.7, "real"),
    ("coastal_dummy", "해안 여부", "natural_geography", 1.0, "static_reference"),
    ("island_ratio", "도서성 비율", "natural_geography", 0.0, "static_reference"),
    ("forest_ratio", "산림 비율", "natural_geography", 0.6412, "static_reference"),
    ("farmland_ratio", "농지 비율", "natural_geography", 0.1874, "static_reference"),
    ("terrain_relief", "지형 기복", "natural_geography", 412.0, "static_reference"),
    ("annual_mean_temperature", "연평균기온", "climate", 13.1, "proxy"),
    ("annual_temperature_range", "연교차", "climate", 27.4, "proxy"),
    ("annual_precipitation", "연강수량", "climate", 1201.3, "proxy"),
    ("manufacturing_worker_ratio", "제조업 종사자 비율", "industry_structure", 0.2814, "real"),
    ("construction_logistics_worker_ratio", "건설·물류 종사자 비율", "industry_structure", 0.1327, "real"),
    ("knowledge_public_service_worker_ratio", "지식·공공서비스 종사자 비율", "industry_structure", 0.3105, "real"),
]


def _structure_features() -> list[dict[str, Any]]:
    """요인 가중치를 요인 안의 변수 수로 나눠 개별 가중치를 만든다."""
    per_group: dict[str, int] = {}
    for _, _, group, _, _ in _FEATURES:
        per_group[group] = per_group.get(group, 0) + 1
    return [
        {
            "feature": feature,
            "label": label,
            "value": value,
            "group": group,
            "weight": round(GROUP_WEIGHTS[group] / per_group[group], 4),
            "source_type": source_type,
            "missing_reason": None,
        }
        for feature, label, group, value, source_type in _FEATURES
    ]


PROVENANCE: list[dict[str, Any]] = [
    {
        "name": "지역 마스터",
        "source_type": "real",
        "endpoint": "KorService2 /areaBasedList2 lDongRegnCd·lDongSignguCd",
        "reference_period": "2026-08-17 수집분",
        "row_count": 230,
        "note": "KTO 실제 관광자원 lDong 5자리 코드 기준. 일반구는 모 시로 합산",
    },
    {
        "name": "인구·면적·사업체",
        "source_type": "real",
        "endpoint": "SGIS OpenAPI3 population.json · hadmarea.geojson · company.json",
        "reference_period": "인구 2020 총조사, 사업체 2024",
        "row_count": 230,
        "note": "면적은 경계 GeoJSON에 shoelace 공식 적용",
    },
    {
        "name": "해안·도서 여부",
        "source_type": "static_reference",
        "endpoint": "data/reference/coastal_island.csv",
        "reference_period": "2026년 행정구역 기준",
        "row_count": 76,
        "note": "원천 여건. 직접 정리한 표",
    },
    {
        "name": "기후평년값",
        "source_type": "proxy",
        "endpoint": "data/processed/kma_climate_normals_by_region.csv",
        "reference_period": "1991~2020 기상청 기후평년값",
        "row_count": 230,
        "note": "가까운 관측소 3개 역거리 제곱 보간. 중심점이 자원 좌표 중앙값이라 proxy",
    },
    {
        "name": "지형 기복",
        "source_type": "static_reference",
        "endpoint": "data/processed/dem_terrain_relief_by_region.csv",
        "reference_period": "국토지리정보원 한반도 90m DEM",
        "row_count": 230,
        "note": "시군구 경계 내 P90 고도-P10 고도",
    },
    {
        "name": "토지피복",
        "source_type": "static_reference",
        "endpoint": "data/processed/land_cover_by_region.csv",
        "reference_period": "2024년 기준 국가토지피복통계",
        "row_count": 230,
        "note": "산림=활엽수림+침엽수림+혼효림, 농지=논·밭·시설재배지·과수원 등",
    },
]


def structure_profile() -> dict[str, Any]:
    return {
        "target": REGIONS[0],
        "feature_count": len(_FEATURES),
        "group_weights": GROUP_WEIGHTS,
        "features": _structure_features(),
        "provenance": PROVENANCE,
    }


# ---------------------------------------------------------------------------
# 관광자원 포트폴리오 — gap_analyzer.content_types 의 8유형
# ---------------------------------------------------------------------------
_PORTFOLIO_COUNTS: list[tuple[int, str, int]] = [
    (12, "관광지", 412),
    (14, "문화시설", 118),
    (15, "행사/공연/축제", 96),
    (25, "여행코스", 34),
    (28, "레포츠", 87),
    (32, "숙박", 264),
    (38, "쇼핑", 143),
    (39, "음식점", 553),
]

_AREA_SQUARE_KM = 1324.39


def portfolio_report() -> dict[str, Any]:
    total = sum(count for _, _, count in _PORTFOLIO_COUNTS)
    return {
        "region_name": "경주시",
        "area_code": "35",
        "sigungu_code": "2",
        "area_square_km": _AREA_SQUARE_KM,
        "total_resource_count": total,
        "total_count_per_square_km": round(total / _AREA_SQUARE_KM, 4),
        "metrics": [
            {
                "content_type_id": type_id,
                "content_type_name": name,
                "count": count,
                "percentage": round(count / total * 100, 4),
                "count_per_square_km": round(count / _AREA_SQUARE_KM, 4),
            }
            for type_id, name, count in _PORTFOLIO_COUNTS
        ],
    }


# ---------------------------------------------------------------------------
# 중심 관광지
# ---------------------------------------------------------------------------
HUB_REPORT: dict[str, Any] = {
    "region_name": "경주시",
    "base_year_month": "202606",
    "area_code": "35",
    "sigungu_code": "2",
    "limit": 5,
    "extracted_count": 5,
    "spots": [
        {"rank": 1, "tourist_spot_code": "A02020600", "name": "불국사", "category_large": "인문관광", "category_middle": "역사관광", "category_small": "사찰", "longitude": 129.3320, "latitude": 35.7900},
        {"rank": 2, "tourist_spot_code": "A02020700", "name": "석굴암", "category_large": "인문관광", "category_middle": "역사관광", "category_small": "사찰", "longitude": 129.3494, "latitude": 35.7950},
        {"rank": 3, "tourist_spot_code": "A02010800", "name": "동궁과 월지", "category_large": "인문관광", "category_middle": "역사관광", "category_small": "유적지", "longitude": 129.2265, "latitude": 35.8348},
        {"rank": 4, "tourist_spot_code": "A02010900", "name": "첨성대", "category_large": "인문관광", "category_middle": "역사관광", "category_small": "유적지", "longitude": 129.2190, "latitude": 35.8347},
        {"rank": 5, "tourist_spot_code": "A02030200", "name": "보문관광단지", "category_large": "인문관광", "category_middle": "휴양관광", "category_small": "관광단지", "longitude": 129.2841, "latitude": 35.8420},
    ],
}


# ---------------------------------------------------------------------------
# 성과 평가
# ---------------------------------------------------------------------------
PERFORMANCE_SCORE: dict[str, Any] = {
    "region_name": "경주시",
    "analysis_period": "20250101~20251231",
    "visitor_sum": 41537820.0,
    "resource_demand": 0.7412,
    "demand_intensity": 0.6885,
    "visitor_percentile": 0.9612,
    "resource_demand_percentile": 0.8104,
    "demand_intensity_percentile": 0.7326,
    "composite_score": 0.8483,
    "data_quality": {
        "unavailable_metrics": [],
        "note": (
            "산출하지 못한 지표는 결측으로 둡니다. 0으로 채우면 '성과 바닥'이 되어 "
            "순위가 뒤집힙니다."
        ),
    },
}


# ---------------------------------------------------------------------------
# 지역 비교
# ---------------------------------------------------------------------------
_COMPARE_FIXTURES: dict[str, dict[str, Any]] = {
    "47130": {"area": 1324.39, "total": 1707, "score": 0.9612, "similarity": None},
    "47110": {"area": 1130.06, "total": 1289, "score": 0.8140, "similarity": 0.7280},
    "44210": {"area": 741.34, "total": 604, "score": 0.6023, "similarity": 0.7230},
    "44270": {"area": 694.62, "total": 512, "score": 0.5481, "similarity": 0.7115},
    "52130": {"area": 396.51, "total": 731, "score": 0.6644, "similarity": 0.6794},
}

_DEFAULT_COMPARE = {"area": 500.0, "total": 480, "score": None, "similarity": None}


def comparison_result(region_ids: list[str]) -> dict[str, Any]:
    by_id = {region["region_id"]: region for region in REGIONS}
    columns = []
    for index, region_id in enumerate(region_ids):
        region = by_id.get(
            region_id,
            {
                "region_id": region_id,
                "province_name": "예시 시도",
                "region_name": "예시 시군구",
                "administrative_type": "시",
            },
        )
        fixture = _COMPARE_FIXTURES.get(region_id, _DEFAULT_COMPARE)
        total = fixture["total"]
        area = fixture["area"]
        columns.append(
            {
                "region": region,
                "area_square_km": area,
                "total_resource_count": total,
                "total_count_per_square_km": round(total / area, 4),
                "composite_score": fixture["score"],
                "similarity_to_first": None if index == 0 else fixture["similarity"],
                "portfolio_metrics": [
                    {
                        "content_type_id": type_id,
                        "content_type_name": name,
                        "count": round(count * total / 1707),
                        "percentage": round(count / 1707 * 100, 4),
                        "count_per_square_km": round(count * total / 1707 / area, 4),
                    }
                    for type_id, name, count in _PORTFOLIO_COUNTS
                ],
            }
        )
    return {
        "columns": columns,
        "limitations": [
            "성과 점수는 이동통신 기반 방문자 수만 반영한 잠정값입니다.",
            EXAMPLE_NOTICE,
        ],
    }
