"""지역 마스터와 구조 특성 응답."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .common import ProvenanceRecord, RegionRef, SourceType


class ProvinceSummary(BaseModel):
    """시·도 하나."""

    province_name: str = Field(examples=["강원특별자치도"])
    region_count: int = Field(examples=[18], description="분석 대상 시군구 수")


class RegionSummary(RegionRef):
    """지역 요약."""


class RegionDetail(RegionRef):
    """지역 상세."""

    area_km2: float | None = Field(default=None, examples=[1324.39])
    total_population: int | None = Field(default=None, examples=[248326])
    coastal: bool = Field(examples=[True], description="해안 여부")


class StructureFeature(BaseModel):
    """구조 변수 하나."""

    feature: str = Field(examples=["forest_ratio"])
    label: str = Field(examples=["산림 비율"])
    value: float | None = Field(default=None, examples=[0.6412])
    group: str = Field(examples=["natural_geography"])
    weight: float = Field(examples=[0.06], description="정규화된 개별 가중치")
    source_type: SourceType | None = None
    missing_reason: str | None = Field(default=None, examples=[None])


class StructureProfile(BaseModel):
    """구조 변수 17개와 출처."""

    target: RegionRef
    feature_count: int = Field(examples=[17])
    group_weights: dict[str, float] = Field(
        examples=[
            {
                "regional_scale": 0.10,
                "urban_concentration": 0.10,
                "population_structure": 0.10,
                "natural_geography": 0.30,
                "climate": 0.15,
                "industry_structure": 0.25,
            }
        ]
    )
    features: list[StructureFeature]
    provenance: list[ProvenanceRecord]
