"""분석 파이프라인의 모든 조정 가능한 값.

기획이 확정되지 않은 항목(가중치, k, 지표 선택)은 전부 여기 모아 두고
다른 모듈은 이 값을 읽기만 한다. 실험할 때는 이 파일만 고치면 된다.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = PROJECT_ROOT.parents[2]
DATA_DIR = PROJECT_ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
PROCESSED_DIR = DATA_DIR / "processed"
REFERENCE_DIR = DATA_DIR / "reference"


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


@dataclass(frozen=True)
class Config:
    similarity: SimilarityConfig = field(default_factory=SimilarityConfig)
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
    # 루트 분석기에서 이미 쓰는 키 이름도 지원한다. 중첩 프로젝트의 과거
    # 이름(DATA_GO_KR_SERVICE_KEY)을 강제하면 같은 KorService 권한 키를
    # .env에 중복 저장하게 되기 때문이다.
    key = (
        os.environ.get("DATA_GO_KR_SERVICE_KEY", "").strip()
        or os.environ.get("TOUR_API_SERVICE_KEY", "").strip()
        or os.environ.get("KOR_TOUR_API_SERVICE_KEY", "").strip()
    )
    if not key:
        raise RuntimeError(
            "TOUR_API_SERVICE_KEY(또는 DATA_GO_KR_SERVICE_KEY)가 없습니다. .env를 확인하세요."
        )
    return key


def load_project_environment() -> Path | None:
    """Load the repository dotenv for both the standalone and root CLI paths."""
    from dotenv import load_dotenv

    for path in (REPOSITORY_ROOT / ".env", PROJECT_ROOT / ".env"):
        if path.exists():
            load_dotenv(path, override=False)
            return path
    return None


def sgis_credentials() -> tuple[str, str] | None:
    key = os.environ.get("SGIS_CONSUMER_KEY", "").strip()
    secret = os.environ.get("SGIS_CONSUMER_SECRET", "").strip()
    if key and secret:
        return key, secret
    return None


def env_allows_mock_structural() -> bool:
    value = os.environ.get("TOURGAP_ALLOW_MOCK_STRUCTURAL", "").strip().lower()
    return value in {"1", "true", "yes", "y"}
