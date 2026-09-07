"""여러 도메인이 함께 쓰는 응답 조각."""

from __future__ import annotations

from enum import Enum
from typing import Generic, TypeVar

from pydantic import BaseModel, Field

ItemT = TypeVar("ItemT")


class SourceType(str, Enum):
    """값의 출처 유형."""

    REAL = "real"
    PROXY = "proxy"
    STATIC_REFERENCE = "static_reference"
    MOCK = "mock"


class AdministrativeType(str, Enum):
    SI = "시"
    GUN = "군"
    GU = "자치구"


class ContentType(str, Enum):
    """관광 콘텐츠 6유형."""

    FOOD = "음식"
    LODGING = "숙박"
    CULTURE = "문화관광"
    EXPERIENCE = "체험관광"
    LEISURE = "레저스포츠"
    SHOPPING = "쇼핑"


class RegionRef(BaseModel):
    """지역 식별 정보."""

    region_id: str = Field(pattern=r"^\d{5}$", examples=["47130"])
    province_name: str = Field(examples=["경상북도"])
    region_name: str = Field(examples=["경주시"])
    administrative_type: AdministrativeType = Field(examples=["시"])


class ProvenanceRecord(BaseModel):
    """데이터 출처 한 건."""

    name: str = Field(examples=["지역 마스터"])
    source_type: SourceType
    endpoint: str = Field(examples=["KorService2 /areaBasedList2 lDongRegnCd·lDongSignguCd"])
    reference_period: str = Field(examples=["2026-08-17 수집분"])
    row_count: int | None = Field(default=None, examples=[230])
    note: str = Field(default="", examples=["KTO 실제 관광자원 lDong 5자리 코드 기준"])


class Page(BaseModel, Generic[ItemT]):
    """목록 응답."""

    items: list[ItemT]
    total: int = Field(examples=[230])
