"""분석 파이프라인의 모든 조정 가능한 값.

기획이 확정되지 않은 항목(가중치, k, 지표 선택)은 전부 여기 모아 두고
다른 모듈은 이 값을 읽기만 한다. 실험할 때는 이 파일만 고치면 된다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REFERENCE_DIR = DATA_DIR / "reference"
RESULTS_DIR = PROJECT_ROOT / "results"


# ---------------------------------------------------------------------------
# 과제 1 확정 구조 변수
# ---------------------------------------------------------------------------
SIMILARITY_FEATURES: tuple[str, ...] = (
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
)

FEATURE_GROUPS: dict[str, tuple[str, ...]] = {
    # 상관성이 높은 관측값을 하나의 하위 요인으로 묶어, 같은 현상을
    # 여러 번 센 탓에 도시 규모가 과대 반영되지 않게 한다.
    "regional_scale": (
        "area_km2",
        "total_population",
    ),
    "urban_concentration": (
        "population_density",
        "urbanization_ratio",
        "business_density",
    ),
    "population_structure": ("average_age",),
    "natural_geography": (
        "coastal_dummy",
        "island_ratio",
        "forest_ratio",
        "farmland_ratio",
        "terrain_relief",
    ),
    "climate": (
        "annual_mean_temperature",
        "annual_temperature_range",
        "annual_precipitation",
    ),
    "industry_structure": (
        "manufacturing_worker_ratio",
        "construction_logistics_worker_ratio",
        "knowledge_public_service_worker_ratio",
    ),
}

GROUP_WEIGHTS: dict[str, float] = {
    "regional_scale": 0.10,
    "urban_concentration": 0.10,
    "population_structure": 0.10,
    "natural_geography": 0.30,
    "climate": 0.15,
    "industry_structure": 0.25,
}

LOG_TRANSFORM_COLUMNS: tuple[str, ...] = (
    "area_km2",
    "total_population",
    "population_density",
    "business_density",
    "annual_precipitation",
    "terrain_relief",
)

REFERENCE_YEARS: dict[str, str] = {
    "population": "SGIS latest common supported year",
    "company": "2024",
    "climate": "1991-2020 climate normals",
}

INDUSTRY_GROUPS: dict[str, tuple[str, ...]] = {
    "manufacturing": ("C",),
    "construction_logistics": ("F", "H"),
    "knowledge_public_service": ("J", "K", "M", "N", "O", "P", "Q"),
}

EXCLUDED_INDUSTRIES: tuple[str, ...] = ("I", "R")

MIN_SIMILARITY = 0.40
DEFAULT_K = 15


# ---------------------------------------------------------------------------
# 관광 콘텐츠 분류 (TourAPI 신분류체계 lclsSystm1)
# ---------------------------------------------------------------------------
# 공식 명칭은 KorService2/lclsSystmCode2 에서 확인했다(2026-08-17).
LCLS1_NAMES: dict[str, str] = {
    "NA": "자연관광",
    "HS": "역사관광",
    "VE": "문화관광",
    "EX": "체험관광",
    "LS": "레저스포츠",
    "EV": "축제/공연/행사",
    "SH": "쇼핑",
    "FD": "음식",
    "AC": "숙박",
    "C01": "추천코스",
}

# 정책·사업으로 만들 수 있는 콘텐츠 → 공백 랭킹 대상.
GAP_CATEGORIES: tuple[str, ...] = ("EX", "VE", "LS", "EV", "SH", "FD", "AC")

# 원천 자원(endowment)에 가까움 → 랭킹에서 빼고 맥락으로만 보여 준다.
# 유사성 변수로도 쓰지 않는다(원칙 1: 공백의 output을 input에 넣지 않는다).
CONTEXT_CATEGORIES: tuple[str, ...] = ("NA", "HS")

# 전국 59건뿐이라 시군구 단위 비교가 무의미하다.
EXCLUDED_CATEGORIES: tuple[str, ...] = ("C01",)


# ---------------------------------------------------------------------------
# 유사성 (peer 탐색)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class SimilarityConfig:
    """유사성 feature 그룹과 가중치.

    그룹 weight의 합은 1이 아니어도 된다(내부에서 정규화한다).
    각 그룹 안에서는 feature마다 동일 가중치를 준 뒤 그룹 weight를 곱한다.
    """

    feature_groups: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: dict(FEATURE_GROUPS)
    )
    group_weights: dict[str, float] = field(default_factory=lambda: dict(GROUP_WEIGHTS))
    feature_weights: dict[str, float] = field(default_factory=dict)
    log_transform_columns: tuple[str, ...] = LOG_TRANSFORM_COLUMNS
    peer_k: int = DEFAULT_K
    min_similarity: float = MIN_SIMILARITY
    allow_mock_structural: bool = False
    # 군에 광역시 자치구가 붙는 사고를 막는다. 끄면 순수 거리만 사용.
    same_administrative_type: bool = True


# ---------------------------------------------------------------------------
# 우수성 (benchmark 선정)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class PerformanceConfig:
    #: 목표 가중치. 데이터가 없는 지표(전부 결측)는 자동으로 빠지고
    #: 남은 지표끼리 다시 정규화된다. 그래서 체류·소비 강도가 공개되면
    #: 여기 손대지 않아도 바로 반영된다.
    weights: dict[str, float] = field(
        default_factory=lambda: {
            "stay_intensity": 0.25,  # AreaTarDemDsService — 데이터 미공개
            "consumption_intensity": 0.25,  # AreaTarDemDsService — 데이터 미공개
            "visitor_yoy_growth": 0.20,
            "outsider_ratio": 0.15,
            "visitor_level": 0.10,
            "foreign_ratio": 0.05,
        }
    )
    #: 분포가 크게 치우쳐 z를 내기 전에 로그를 씌울 지표.
    log_scaled: tuple[str, ...] = ("visitor_level",)
    # "national": 전국 분포로 z를 내고 peer 안에서 순위만 매긴다(기본).
    #   peer 15개로 z를 내면 표본이 작아 점수가 튄다.
    #   전국 z를 써도 "전국 1등을 뽑는" 문제는 생기지 않는다.
    #   후보 자체가 이미 peer group으로 제한돼 있기 때문이다.
    # "peer": 명세 원문대로 peer group 내부에서 표준화.
    normalize_scope: str = "national"
    benchmark_k: int = 4


# ---------------------------------------------------------------------------
# 공백 산정
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class GapConfig:
    # 공백 비교의 중심 지표.
    #   share          구성비. 지자체별 API 등록 성실도 차이를 상당 부분 상쇄한다(기본).
    #   per_10k_pop    인구 1만 명당 개수
    #   per_100km2     100km2당 개수
    #   raw_count      단순 개수 (권장하지 않음)
    primary_metric: str = "share"
    secondary_metrics: tuple[str, ...] = ("per_10k_pop", "per_100km2", "raw_count")
    # benchmark 대표값. 이상치에 강한 median을 기본으로 한다.
    aggregate: str = "median"
    # 상위 공백 몇 개까지 중분류로 파고들지.
    drilldown_top_n: int = 3
    drilldown_min_count: int = 3
    # 수요 보정 계수의 범위. 수요 데이터가 없으면 1.0 고정.
    demand_multiplier_range: tuple[float, float] = (0.5, 1.5)
    epsilon: float = 1e-9


# ---------------------------------------------------------------------------
# 데이터 품질 경고 임계값 (P1: TourAPI 등록 건수 != 실제 공급)
# ---------------------------------------------------------------------------
@dataclass(frozen=True)
class QualityConfig:
    min_total_resources: int = 30
    stale_years: int = 2
    min_fresh_ratio: float = 0.20


@dataclass(frozen=True)
class Config:
    similarity: SimilarityConfig = field(default_factory=SimilarityConfig)
    performance: PerformanceConfig = field(default_factory=PerformanceConfig)
    gap: GapConfig = field(default_factory=GapConfig)
    quality: QualityConfig = field(default_factory=QualityConfig)
    # 접근성 기준이 되는 대도시(수도권/광역시). 중심점 좌표는 WGS84.
    gateway_cities: dict[str, tuple[float, float]] = field(
        default_factory=lambda: {
            "서울": (126.9780, 37.5665),
            "부산": (129.0756, 35.1796),
            "대구": (128.6014, 35.8714),
            "인천": (126.7052, 37.4563),
            "광주": (126.8526, 35.1595),
            "대전": (127.3845, 36.3504),
        }
    )
    sgis_year: str = "2020"
    sgis_company_year: str = "2024"
    sgis_industry_class_deg: str = "11"
    industry_groups: dict[str, tuple[str, ...]] = field(
        default_factory=lambda: dict(INDUSTRY_GROUPS)
    )
    excluded_industries: tuple[str, ...] = EXCLUDED_INDUSTRIES


_ACTIVE = Config()


def get_config() -> Config:
    """현재 설정.

    모듈 최상단에서 `from .config import CONFIG` 처럼 값을 붙잡아 두면
    CLI 인자로 설정을 바꿔도 반영되지 않는다. 항상 함수 안에서
    get_config()를 불러 쓴다.
    """
    return _ACTIVE


def set_config(config: Config) -> None:
    global _ACTIVE
    _ACTIVE = config


def data_go_kr_key() -> str:
    key = os.environ.get("DATA_GO_KR_SERVICE_KEY", "").strip()
    if not key:
        raise RuntimeError("DATA_GO_KR_SERVICE_KEY가 없습니다. .env를 확인하세요.")
    return key


def sgis_credentials() -> tuple[str, str] | None:
    key = os.environ.get("SGIS_CONSUMER_KEY", "").strip()
    secret = os.environ.get("SGIS_CONSUMER_SECRET", "").strip()
    if key and secret:
        return key, secret
    return None


def env_allows_mock_structural() -> bool:
    value = os.environ.get("TOURGAP_ALLOW_MOCK_STRUCTURAL", "").strip().lower()
    return value in {"1", "true", "yes", "y"}
