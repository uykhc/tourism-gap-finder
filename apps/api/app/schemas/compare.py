"""여러 지역을 나란히 놓는 비교 응답."""

from __future__ import annotations

from pydantic import BaseModel, Field

from .analysis import PortfolioMetric
from .common import RegionRef


class ComparisonColumn(BaseModel):
    """비교표의 한 열."""

    region: RegionRef
    area_square_km: float | None = Field(default=None, examples=[1324.39])
    total_resource_count: int | None = Field(default=None, examples=[1707])
    total_count_per_square_km: float | None = Field(default=None, examples=[1.2889])
    composite_score: float | None = Field(default=None, examples=[0.9612])
    similarity_to_first: float | None = Field(
        default=None, examples=[None], description="첫 번째 지역과의 구조 유사도"
    )
    portfolio_metrics: list[PortfolioMetric]


class ComparisonResult(BaseModel):
    """지역 비교표."""

    columns: list[ComparisonColumn]
    limitations: list[str] = Field(
        examples=[["성과 점수는 이동통신 기반 방문자 수만 반영한 잠정값입니다."]]
    )
