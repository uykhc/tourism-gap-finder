"""스텁 엔드포인트가 돌려주는 고정 예시 payload.

분석 함수를 붙이기 전까지 프론트가 화면을 만들 수 있도록 두는 자리다.
형태는 실제 산출물과 같게 유지한다 — peer 목록은
``data/analysis/similarity/results/경주시_47130_20260817/peers.csv``의 실제 값,
나머지는 각 분석 모듈이 반환하는 dict 구조를 그대로 따랐다.

여기 있는 숫자는 **화면 개발용 표본**이며 정책 판단에 쓰면 안 된다.
각 응답의 ``status``/``limitations``/``data_quality``가 그 사실을 함께 나른다.
실제 연결 시 이 모듈 전체를 지우고 라우터의 TODO 지점을 채운다.
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

REGION_TOTAL = 230

PROVINCES: list[dict[str, Any]] = [
    {"province_name": "서울특별시", "region_count": 25},
    {"province_name": "부산광역시", "region_count": 16},
    {"province_name": "대구광역시", "region_count": 9},
    {"province_name": "인천광역시", "region_count": 11},
    {"province_name": "광주광역시", "region_count": 5},
    {"province_name": "대전광역시", "region_count": 5},
    {"province_name": "울산광역시", "region_count": 5},
    {"province_name": "세종특별자치시", "region_count": 1},
    {"province_name": "경기도", "region_count": 31},
    {"province_name": "강원특별자치도", "region_count": 18},
    {"province_name": "충청북도", "region_count": 11},
    {"province_name": "충청남도", "region_count": 15},
    {"province_name": "전북특별자치도", "region_count": 14},
    {"province_name": "전라남도", "region_count": 22},
    {"province_name": "경상북도", "region_count": 22},
    {"province_name": "경상남도", "region_count": 18},
    {"province_name": "제주특별자치도", "region_count": 2},
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
# 유사 지역 — results/경주시_47130_20260817/peers.csv 실제 값
# ---------------------------------------------------------------------------
_PEER_ROWS: list[tuple[int, str, str, str, str, float, float]] = [
    (1, "47110", "경상북도", "포항시", "시", 0.3174, 0.7280),
    (2, "44210", "충청남도", "서산시", "시", 0.3244, 0.7230),
    (3, "44270", "충청남도", "당진시", "시", 0.3404, 0.7115),
    (4, "52130", "전북특별자치도", "군산시", "시", 0.3866, 0.6794),
    (5, "12150", "전라남도", "순천시", "시", 0.3869, 0.6792),
    (6, "12130", "전라남도", "여수시", "시", 0.4361, 0.6465),
    (7, "48240", "경상남도", "사천시", "시", 0.4590, 0.6319),
    (8, "51150", "강원특별자치도", "강릉시", "시", 0.5243, 0.5920),
    (9, "52210", "전북특별자치도", "김제시", "시", 0.5683, 0.5665),
    (10, "12190", "전라남도", "광양시", "시", 0.5691, 0.5660),
    (11, "43130", "충청북도", "충주시", "시", 0.5742, 0.5632),
    (12, "51110", "강원특별자치도", "춘천시", "시", 0.5938, 0.5522),
    (13, "52140", "전북특별자치도", "익산시", "시", 0.6063, 0.5454),
    (14, "47150", "경상북도", "김천시", "시", 0.6217, 0.5370),
    (15, "47170", "경상북도", "안동시", "시", 0.6246, 0.5355),
]

STRUCTURAL_CANDIDATE_WARNING = (
    "이 목록은 구조적으로 유사한 후보입니다. "
    "관광 성과 검증 전에는 '우수 Peer'로 해석하지 않습니다."
)


def peer_result(*, k: int, min_similarity: float) -> dict[str, Any]:
    peers = [
        {
            "rank": rank,
            "region_id": region_id,
            "province_name": province,
            "region_name": name,
            "administrative_type": admin_type,
            "similarity": similarity,
            "distance": distance,
            "feature_weight_used": 1.0,
            "missing_feature_count": 0,
        }
        for rank, region_id, province, name, admin_type, distance, similarity in _PEER_ROWS
        if similarity >= min_similarity
    ][:k]
    return {
        "result_version": "2026-09-05",
        "target": REGIONS[0],
        "selection_type": "structural_similarity_candidates",
        "warning": STRUCTURAL_CANDIDATE_WARNING,
        "requested_k": k,
        "min_similarity": min_similarity,
        "peers": peers,
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
    "resource_demand": None,
    "demand_intensity": None,
    "visitor_percentile": 0.9612,
    "resource_demand_percentile": None,
    "demand_intensity_percentile": None,
    "composite_score": 0.9612,
    "data_quality": {
        "unavailable_metrics": ["resource_demand", "demand_intensity"],
        "note": (
            "AreaTarResDemService·AreaTarDemDsService·AreaTarDivService는 등록됐지만 "
            "전 지역·전 기간 0건을 반환합니다. 결측을 0으로 채우면 순위가 뒤집히므로 "
            "해당 지표는 산출하지 않고 방문자 수만 반영했습니다."
        ),
    },
}


# ---------------------------------------------------------------------------
# 관광 공백 — datalab_navigation 의 두 리포트를 합친 형태
# ---------------------------------------------------------------------------
_GAP_ROWS: list[tuple[str, int, float, float, list[tuple[str, float, float]]]] = [
    # (유형, 대상 장소수, 구성비, 100㎢당 밀도, [(peer, peer 구성비, peer 밀도)])
    ("체험관광", 87, 0.1312, 6.5690, [("포항시", 0.1842, 9.4400), ("서산시", 0.1615, 8.1200)]),
    ("쇼핑", 143, 0.2157, 10.7970, [("포항시", 0.2384, 12.2100), ("서산시", 0.1902, 9.5600)]),
    ("레저스포츠", 96, 0.1448, 7.2490, [("포항시", 0.1391, 7.1300), ("서산시", 0.1502, 7.5500)]),
    ("문화관광", 118, 0.1780, 8.9100, [("포항시", 0.1264, 6.4800), ("서산시", 0.1188, 5.9700)]),
    ("숙박", 264, 0.3982, 19.9340, [("포항시", 0.2719, 13.9300), ("서산시", 0.3103, 15.6000)]),
    ("음식", 553, 0.8343, 41.7550, [("포항시", 0.9012, 46.1700), ("서산시", 0.8221, 41.3300)]),
]


def _ratio(target: float, peer: float) -> float | None:
    return round(target / peer, 4) if peer else None


def gap_report() -> dict[str, Any]:
    comparisons = []
    for content_type, place_count, share, density, peers in _GAP_ROWS:
        per_peer = []
        for peer_name, peer_share, peer_density in peers:
            composition_lower = share < peer_share
            density_lower = density < peer_density
            per_peer.append(
                {
                    "peer_region": peer_name,
                    "peer_composition_share": peer_share,
                    "peer_density_per_100_km2": peer_density,
                    "target_to_peer_composition_ratio": _ratio(share, peer_share),
                    "target_to_peer_density_ratio": _ratio(density, peer_density),
                    "is_target_composition_lower": composition_lower,
                    "is_target_density_lower": density_lower,
                    "is_relative_supply_gap_candidate": composition_lower or density_lower,
                }
            )
        candidates = [item for item in per_peer if item["is_relative_supply_gap_candidate"]]
        ratios = [
            ratio
            for item in candidates
            for ratio in (
                item["target_to_peer_composition_ratio"],
                item["target_to_peer_density_ratio"],
            )
            if ratio is not None
        ]
        comparisons.append(
            {
                "content_type": content_type,
                "target_place_count": place_count,
                "target_composition_share": share,
                "target_density_per_100_km2": density,
                "individual_peer_comparisons": per_peer,
                "candidate_peer_regions": [item["peer_region"] for item in candidates],
                "candidate_peer_count": len(candidates),
                "lowest_target_to_peer_supply_ratio": min(ratios, default=None),
            }
        )
    comparisons.sort(
        key=lambda item: (
            -item["candidate_peer_count"],
            item["lowest_target_to_peer_supply_ratio"] is None,
            item["lowest_target_to_peer_supply_ratio"] or float("inf"),
            item["content_type"],
        )
    )

    pressure_metrics = sorted(
        (
            {
                "content_type": content_type,
                "navigation_search_count": searches,
                "kakao_supply_place_count": places,
                "searches_per_place": round(searches / places, 4),
            }
            for content_type, searches, places in [
                ("체험관광", 184230, 87),
                ("숙박", 402118, 264),
                ("쇼핑", 178440, 143),
                ("레저스포츠", 96204, 96),
                ("문화관광", 108932, 118),
                ("음식", 481226, 553),
            ]
        ),
        key=lambda item: (-item["searches_per_place"], item["content_type"]),
    )

    return {
        "target": REGIONS[0],
        "relative_supply": {
            "analysis_type": "relative_supply_gap_by_individual_peer",
            "status": "provisional",
            "target_region": REGIONS[0],
            "peer_regions": [REGIONS[1], REGIONS[2]],
            "comparison_rule": (
                "각 Peer와 비교해 유형별 공급 구성비 또는 100㎢당 공급밀도가 낮으면 "
                "상대적 빈칸 후보로 표시합니다."
            ),
            "content_type_comparisons": comparisons,
            "priority_order_by_relative_supply_gap": [
                item["content_type"] for item in comparisons if item["candidate_peer_count"]
            ],
            "limitations": [
                "Peer는 구조적 유사 후보이며 관광 성과가 검증된 우수 Peer가 아닙니다.",
                EXAMPLE_NOTICE,
            ],
        },
        "supply_pressure": {
            "report_version": "2026-09-05",
            "region_name": "경주시",
            "analysis_period": {
                "selection": "latest_available_months",
                "month_count": 12,
                "start_ym": "202508",
                "end_ym": "202607",
            },
            "metric_definition": "유형별 내비게이션 목적지 검색량 ÷ 카카오맵 유형별 장소 수",
            "content_type_metrics": pressure_metrics,
            "priority_order_by_supply_pressure": [
                item["content_type"] for item in pressure_metrics
            ],
            "warnings": [
                "기타관광은 분석에서 제외했으며 원본 검색량 합계에는 포함됩니다.",
                EXAMPLE_NOTICE,
            ],
        },
    }


# ---------------------------------------------------------------------------
# AI 빈칸 리포트 — config/ai/tourism_gap_report.schema.json
# ---------------------------------------------------------------------------
_BENCHMARKS: list[dict[str, Any]] = [
    {**REGIONS[1], "rank": 1, "similarity": 0.7280, "performance_score": 0.8140},
    {**REGIONS[2], "rank": 2, "similarity": 0.7230, "performance_score": 0.6023},
]


def tourism_gap_report() -> dict[str, Any]:
    gaps = gap_report()
    relative = gaps["relative_supply"]
    pressure = gaps["supply_pressure"]
    return {
        "report_version": "2026-09-07",
        "status": "provisional",
        "target": REGIONS[0],
        "analysis_period": "202508~202607",
        "headline": (
            "경주시는 비교한 우수 지역 두 곳 모두보다 체험관광 등록 공급이 낮게 관찰되고, "
            "내비게이션 목적지 검색량 대비 등록 장소 수도 6개 유형 중 가장 적습니다. "
            "두 지표를 함께 볼 때 체험관광은 추가 검증 우선순위가 가장 높은 유형입니다."
        ),
        "peers": {
            "selection_type": "structural_similarity_candidates",
            "note": (
                "인구·면적·관광 및 지역 구조 관련 입력변수의 유사성을 기준으로 선정한 "
                "비교 후보이며, 관광상품 구성이나 역사문화도시로서의 성격까지 동일하다는 "
                "의미는 아닙니다."
            ),
            "items": peer_result(k=3, min_similarity=0.40)["peers"],
        },
        "benchmarks": {
            "selection_rule": (
                "유사 지역 중 관광 성과 점수가 대상 지역보다 높은 지역을 최대 3곳까지 선정"
            ),
            "items": _BENCHMARKS,
        },
        "relative_supply": {
            "comparison_rule": relative["comparison_rule"],
            "notes": [
                "구성비는 유형 간 중복 분류를 허용한 관광 관련 장소 전체를 분모로 하므로 "
                "유형별 구성비의 합은 1을 초과할 수 있습니다.",
                "시 전체 면적을 사용한 밀도이므로 실제 관광거점 내 체감 공급밀도와는 "
                "차이가 있을 수 있습니다.",
            ],
            "content_type_comparisons": relative["content_type_comparisons"],
            "priority_order": relative["priority_order_by_relative_supply_gap"],
        },
        "supply_pressure": {
            "metric_definition": (
                "유형별 내비게이션 목적지 검색량 ÷ 카카오맵 유형별 등록 장소 수"
            ),
            "analysis_period": pressure["analysis_period"],
            "notes": [
                "이 지표는 실제 시설 수용능력이나 예약 가능 인원을 뜻하지 않으며, "
                "등록된 장소 1곳당 발생한 검색량을 비교하는 탐색 지표입니다.",
                "유형별 지도 등록 방식과 검색 행태가 다를 수 있으므로 유형 간 순위는 "
                "공급 부족의 확정 판단이 아니라 추가 검증 우선순위로 해석합니다.",
            ],
            "content_type_metrics": pressure["content_type_metrics"],
            "priority_order": pressure["priority_order_by_supply_pressure"],
        },
        **TOURISM_GAP_REPORT_NARRATIVE,
    }


TOURISM_GAP_REPORT_NARRATIVE: dict[str, Any] = {
    "gap_types": [
        {
            "content_type": "체험관광",
            "judgement": (
                "비교한 두 Peer 모두에서 체험관광 등록 공급의 구성비와 면적당 밀도가 낮게 "
                "나타납니다. 동시에 등록 장소 1곳당 목적지 검색량이 가장 높아, 6개 유형 가운데 "
                "추가적인 공급·수요 검증 필요성이 가장 일관되게 나타납니다."
            ),
            "quantitative_evidence": [
                {
                    "metric": "체험관광 100㎢당 공급밀도",
                    "target_value": 6.569,
                    "comparison": "포항시 9.44 대비 0.70배, 서산시 8.12 대비 0.81배",
                },
                {
                    "metric": "체험관광 목적지 검색량 ÷ 장소 수",
                    "target_value": 2117.5862,
                    "comparison": "6개 유형 중 가장 높은 장소당 검색량",
                },
            ],
            "case_refs": [
                {"case_id": "case-01", "relevance_note": None},
                {"case_id": "case-03", "relevance_note": None},
            ],
            "applicability_insight": (
                "경주는 역사문화자원과 주요 관광거점이 이미 형성돼 있어 신규 관광자원을 "
                "만드는 방식뿐 아니라 기존 관람 동선에 참여형·예약형 프로그램을 결합하는 "
                "방식을 우선 검토할 수 있습니다. 다만 현재 지표만으로 어떤 세부 체험이 부족한지는 "
                "알 수 없으므로 역사·가족·공예·야간·실내 체험 등 세부 유형과 관광권역별 공급을 "
                "추가 확인해야 합니다."
            ),
        },
        {
            "content_type": "쇼핑",
            "judgement": (
                "포항시 대비 등록 공급 구성비와 밀도가 낮지만 서산시보다는 높아, "
                "상대적 공급 부족 신호가 한쪽 Peer에서만 관찰됩니다."
            ),
            "quantitative_evidence": [
                {
                    "metric": "쇼핑 공급 구성비",
                    "target_value": 0.2157,
                    "comparison": "포항시 0.2384 대비 0.90배, 서산시 0.1902 대비 1.13배",
                },
                {
                    "metric": "쇼핑 목적지 검색량 ÷ 장소 수",
                    "target_value": 1247.8322,
                    "comparison": "6개 유형 중 3위",
                },
            ],
            "case_refs": [
                {
                    "case_id": "case-03",
                    "relevance_note": (
                        "직접적인 쇼핑 공급 사례가 아니라 체험과 지역 소비를 연계할 때 "
                        "참고할 수 있는 사례"
                    ),
                }
            ],
            "applicability_insight": (
                "두 우수 지역의 상대 공급 방향이 엇갈리므로 쇼핑시설 자체의 부족으로 "
                "판단하기에는 근거가 약합니다. 별도 시설 확대보다 체험 프로그램 이후 "
                "지역상품·상권으로 소비가 이어지는지 관광동선 단위에서 확인하는 편이 적절합니다."
            ),
        },
    ],
    "benchmark_cases": [
        {
            "case_id": "case-01",
            "benchmark_region": "포항시",
            "title": "포항 스페이스워크",
            "case_type": "시설",
            "content_type": "체험관광",
            "period": "2021~",
            "operator": "포스코 · 포항시",
            "summary": (
                "포스코가 환호공원에 총 길이 333m의 체험형 조형물을 조성하고 2021년 "
                "포항시에 기부한 사례입니다. 기존 공원과 해안 전망이라는 장소 자원에 직접 걷고 "
                "오르는 체험 요소를 추가했습니다."
            ),
            "applicability": (
                "기존 집객 거점에 새로운 체험 요소를 결합했다는 점은 참고할 수 있습니다. "
                "다만 스페이스워크 자체는 대형 신규 시설이므로 경주 적용 시에는 동일 규모 "
                "시설을 전제하기보다 기존 관광거점의 체험 기능을 강화했다는 원리를 분리해 "
                "검토해야 합니다."
            ),
            "source_ids": ["src-01"],
        },
        {
            "case_id": "case-02",
            "benchmark_region": "포항시",
            "title": "포항 스틸아트페스티벌",
            "case_type": "프로그램",
            "content_type": "체험관광",
            "period": "2012~",
            "operator": "포항시 · 포항문화재단",
            "summary": (
                "2012년 시작해 철강도시라는 지역 정체성을 예술 콘텐츠와 결합해 반복 개최해 "
                "온 축제 사례입니다. 개최 장소와 프로그램은 연도별로 달라지며, 별도의 상설 "
                "관광시설을 신설하지 않고도 지역 고유 소재를 지속적인 콘텐츠로 전환할 수 "
                "있다는 점에서 참고 가치가 있습니다."
            ),
            "applicability": (
                "경주의 역사문화자원을 단순 관람 대상에 머물게 하지 않고 해설·공예·공연·참여 "
                "프로그램으로 재구성하는 접근을 참고할 수 있습니다. 다만 기존 축제와 프로그램의 "
                "중복 여부와 비수기·야간 등 실제 콘텐츠 공백 시간대를 먼저 확인해야 합니다."
            ),
            "source_ids": ["src-02"],
        },
        {
            "case_id": "case-03",
            "benchmark_region": "서산시",
            "title": "서산 해미읍성 역사체험축제",
            "case_type": "프로그램",
            "content_type": "체험관광",
            "period": "2000~",
            "operator": "서산시",
            "summary": (
                "해미읍성이라는 단일 역사공간을 중심으로 2000년부터 명칭과 프로그램 구성을 "
                "변화시키며 역사·병영 체험형 축제를 반복 운영해 온 사례입니다. 역사자원 자체뿐 "
                "아니라 그 장소에서 무엇을 경험하게 할 것인지를 관광 콘텐츠로 구성한 방식입니다."
            ),
            "applicability": (
                "경주의 개별 유적이나 역사관광권역에서도 상설 구조물을 추가하지 않고 특정 "
                "기간·시간대에 참여형 프로그램을 운영하는 방식은 검토 가능합니다. 다만 "
                "국가유산별 보존·활용 기준과 행사 허가, 동시 수용인원 등을 사전에 확인해야 합니다."
            ),
            "source_ids": ["src-03"],
        },
        {
            "case_id": "case-04",
            "benchmark_region": "포항시",
            "title": "포항국제불빛축제",
            "case_type": "프로그램",
            "content_type": "체험관광",
            "period": "2004~",
            "operator": "포항시 · 포항문화재단",
            "summary": (
                "철강도시 포항을 상징하는 '불'과 '빛'을 테마로 2004년 시작해 반복 개최해 온 "
                "문화관광축제입니다. 이후 불꽃 중심 행사에서 드론·라이트아트 등으로 콘텐츠를 "
                "확장해 지역의 산업 이미지를 야간 관광경험으로 전환해 왔습니다."
            ),
            "applicability": (
                "경주 역시 역사문화라는 명확한 지역 정체성이 있으므로 새로운 테마를 외부에서 "
                "도입하기보다 기존 자원을 야간·참여형 프로그램으로 재해석하는 방식을 검토할 "
                "수 있습니다. 단, 대형 축제를 추가하기보다 기존 야간개방·축제·행사와의 시간대 및 "
                "공간적 공백을 먼저 확인하는 것이 필요합니다."
            ),
            "source_ids": ["src-04"],
        },
    ],
    "closing_insight": {
        "narrative": (
            "경주시는 문화관광과 숙박의 등록 공급 수준은 비교한 우수 지역보다 높게 나타나는 "
            "반면, 체험관광은 두 우수 지역 모두보다 상대적 공급이 낮고 등록 장소 1곳당 목적지 "
            "검색량도 가장 높습니다. 따라서 현재 지표만 놓고 보면 전 관광 유형을 일괄적으로 "
            "확충하기보다 체험관광에서 실제 미충족 수요가 존재하는지 우선 검증하는 접근이 "
            "타당합니다. 다만 카카오맵 등록 장소 수는 실제 프로그램 수나 시설 수용능력을 완전히 "
            "반영하지 않으므로, 체험관광 부족을 확정하기 전에 세부 유형·관광권역·운영시간·"
            "예약 가능량을 추가 확인해야 합니다. 우수 지역 사례에서도 대형 시설형과 반복 "
            "프로그램형이 모두 확인되므로 특정 투자 방식 자체를 모방하기보다 기존 자원에 "
            "새로운 경험을 결합하는 방식과 반복 운영을 통해 콘텐츠를 축적하는 방식을 구분해 "
            "참고할 필요가 있습니다."
        ),
        "focus_points": [
            {
                "order": 1,
                "title": "기존 거점에 체험 요소 덧붙이기",
                "rationale": (
                    "체험관광은 상대 공급과 장소당 검색량 두 신호가 같은 방향을 가리키는 유일한 "
                    "유형입니다. 따라서 신규 시설 건립을 전제로 하기보다 주요 관광거점별로 어떤 "
                    "체험이 이미 있고 어느 시간대·이용자군에서 공백이 발생하는지 먼저 확인할 "
                    "가치가 높습니다."
                ),
                "evidence": [
                    "상대 공급: 우수 지역 2곳 모두보다 낮음, 최저 0.70배",
                    "장소당 검색량: 6개 유형 중 1위 (2,117.6)",
                ],
                "case_ids": ["case-01", "case-03"],
            },
            {
                "order": 2,
                "title": "시설 없이 반복 프로그램으로 공급 늘리기",
                "rationale": (
                    "대규모 시설 투자에 앞서 기존 장소를 활용한 반복 프로그램으로 실제 "
                    "참여수요를 검증하는 경로를 우선 검토할 수 있습니다. 특히 비수기·야간·가족 "
                    "단위 등 구체적인 이용자와 시간대의 공백이 확인될 경우 소규모 실증사업으로 "
                    "효과를 확인한 뒤 확대 여부를 판단하는 방식이 적합합니다."
                ),
                "evidence": [
                    "포항 스틸아트페스티벌은 2012년부터 지역 산업 정체성을 활용한 축제를 반복 운영"
                ],
                "case_ids": ["case-02", "case-04"],
            },
        ],
        "watch_outs": [
            "등록 공급이 적고 장소당 검색량이 높다는 관찰일 뿐, 공급을 늘리면 방문객·체류시간·"
            "소비가 증가한다는 인과는 확인되지 않았습니다.",
            "쇼핑은 우수 지역 두 곳의 상대 공급 방향이 엇갈려 독립적인 공급 부족 유형으로 "
            "판단하기 어렵습니다.",
            "사례는 사업 방식의 참고 자료이며, 해당 사례의 관광성과가 경주에서도 동일하게 "
            "나타날 것이라는 근거는 아닙니다.",
        ],
    },
    "sources": [
        {
            "source_id": "src-01",
            "title": "스페이스워크 완공·조성·기부 관련 공식 자료",
            "publisher": "포스코그룹 뉴스룸",
            "url": "https://newsroom.posco.com/",
            "published_at": "2021-11-18 외",
        },
        {
            "source_id": "src-02",
            "title": "포항스틸아트페스티벌 연혁 공식 안내",
            "publisher": "포항문화재단",
            "url": "https://www.pcf.or.kr/",
            "published_at": "상시 갱신",
        },
        {
            "source_id": "src-03",
            "title": "서산 해미읍성축제 추진 현황 자료",
            "publisher": "서산시",
            "url": "https://www.seosan.go.kr/",
            "published_at": "2024",
        },
        {
            "source_id": "src-04",
            "title": "포항국제불빛축제 공식 안내",
            "publisher": "포항문화재단",
            "url": "https://www.pcf.or.kr/",
            "published_at": "상시 갱신",
        },
    ],
    "limitations": [
        "공급은 카카오맵에 해당 유형으로 등록된 장소 수를 이용한 대리변수이며, 실제 "
        "프로그램 수·운영시간·예약 슬롯·수용인원·품질을 직접 측정하지 않습니다.",
        "목적지 검색량은 관광객의 실제 방문 또는 미충족 수요와 동일하지 않으며, 반복 검색·"
        "지역주민 이용 등 검색행태가 포함될 수 있습니다.",
        "유형별 지도 등록 방식과 검색행태가 서로 달라 `검색량 ÷ 장소 수`의 유형 간 단순 "
        "순위를 실제 공급 부족 규모로 해석해서는 안 됩니다.",
        "시 전체 면적 기준 공급밀도는 관광객이 집중되는 실제 관광권역의 공간적 공급 수준을 "
        "충분히 반영하지 못합니다.",
        "방문자는 이동통신 기반 일별 순방문자로, 2박 3일 체류가 3일로 집계됩니다.",
        "화면 개발용 예시 응답이며 분석 수치 자체는 실제 분석 결과가 아닙니다. 실제 정책 "
        "판단에는 원자료 검증과 관광권역·세부 체험유형·운영능력에 대한 추가 분석이 필요합니다.",
    ],
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
