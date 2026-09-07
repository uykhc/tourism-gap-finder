"""관광 빈칸 종합 리포트."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

from .analysis import AnalysisPeriod, ContentTypeComparison, SupplyPressureMetric
from .common import ContentType, RegionRef
from .peers import PeerItem


class BenchmarkItem(RegionRef):
    """유사 지역 중 성과가 더 높아 비교 기준이 된 지역."""

    rank: int = Field(ge=1, examples=[1])
    similarity: float = Field(ge=0.0, le=1.0, examples=[0.791])
    performance_score: float = Field(examples=[0.8412])


class PeerSection(BaseModel):
    """구조적으로 유사한 지역."""

    selection_type: str = Field(default="structural_similarity_candidates")
    note: str = Field(
        examples=[
            "인구·면적·관광 및 지역 구조 관련 입력변수의 유사성을 기준으로 선정한 "
            "비교 후보이며, 관광상품 구성이나 역사문화도시로서의 성격까지 동일하다는 "
            "의미는 아닙니다."
        ]
    )
    items: list[PeerItem]


class BenchmarkSection(BaseModel):
    """비교 기준이 된 우수 지역."""

    selection_rule: str = Field(
        examples=["유사 지역 중 관광 성과가 대상 지역보다 높은 상위 3곳"]
    )
    items: list[BenchmarkItem]


class RelativeSupplySection(BaseModel):
    """우수 지역 대비 상대적 빈칸."""

    comparison_rule: str = Field(
        examples=[
            "각 우수 지역과 비교해 유형별 공급 구성비 또는 100㎢당 공급밀도가 "
            "낮으면 상대적 빈칸 후보로 표시합니다."
        ]
    )
    notes: list[str] = Field(
        default_factory=list,
        examples=[["시 전체 면적을 사용한 밀도이므로 실제 관광거점 내 체감 공급밀도와는 차이가 있을 수 있습니다."]],
    )
    content_type_comparisons: list[ContentTypeComparison]
    priority_order: list[ContentType] = Field(examples=[["체험관광", "쇼핑"]])


class SupplyPressureSection(BaseModel):
    """수요 대비 절대적 빈칸."""

    metric_definition: str = Field(
        examples=["유형별 내비게이션 목적지 검색량 ÷ 카카오맵 유형별 장소 수"]
    )
    analysis_period: AnalysisPeriod
    notes: list[str] = Field(
        default_factory=list,
        examples=[["실제 시설 수용능력이나 예약 가능 인원을 뜻하지 않습니다."]],
    )
    content_type_metrics: list[SupplyPressureMetric]
    priority_order: list[ContentType] = Field(examples=[["체험관광", "숙박"]])


class QuantitativeEvidence(BaseModel):
    metric: str = Field(min_length=1, examples=["체험관광 100㎢당 공급밀도"])
    target_value: float = Field(examples=[20.37])
    comparison: str = Field(min_length=1, examples=["우수 지역 3곳 모두보다 낮음, 최저 0.65배"])


class CaseRef(BaseModel):
    """benchmark_cases 참조. 유형이 정확히 맞지 않는 사례는 이유를 붙인다."""

    case_id: str = Field(min_length=1, examples=["case-03"])
    relevance_note: str | None = Field(
        default=None,
        examples=["직접적인 쇼핑 공급 사례가 아니라 체험과 지역 소비를 연계할 때 참고할 수 있는 사례"],
    )


class GapType(BaseModel):
    content_type: ContentType = Field(examples=["체험관광"])
    judgement: str = Field(min_length=1, examples=["우수 지역 세 곳 모두에서 체험관광 공급이 낮다."])
    quantitative_evidence: list[QuantitativeEvidence] = Field(min_length=1)
    case_refs: list[CaseRef] = Field(default_factory=list)
    applicability_insight: str = Field(
        min_length=1, examples=["설악산과 해안이 모두 있어 연계 여지가 있다."]
    )


class BenchmarkCase(BaseModel):
    """우수 지역에서 실제로 추진된 관광 사업·정책."""

    case_id: str = Field(min_length=1, examples=["case-01"])
    benchmark_region: str = Field(min_length=1, examples=["포항시"])
    title: str = Field(min_length=1, examples=["포항 스페이스워크"])
    case_type: Literal["사업", "정책", "프로그램", "시설"] = Field(examples=["시설"])
    content_type: ContentType = Field(examples=["체험관광"])
    period: str | None = Field(default=None, examples=["2021~"])
    operator: str | None = Field(default=None, examples=["포항시 · 민간 기부채납"])
    summary: str = Field(min_length=1, examples=["유휴 산업 부지를 체험형 조형·전망 콘텐츠로 전환했다."])
    applicability: str = Field(
        min_length=1, examples=["경주는 역사자원 밀집도가 높아 야간 동선 연계 여지가 있다."]
    )
    source_ids: list[str] = Field(min_length=1, examples=[["src-01"]])


class FocusPoint(BaseModel):
    """우선 검토할 방향."""

    order: int = Field(ge=1, examples=[1])
    title: str = Field(min_length=1, examples=["체험관광 공급 확충"])
    rationale: str = Field(min_length=1, examples=["두 신호가 같은 방향을 가리키는 유일한 유형이다."])
    evidence: list[str] = Field(
        min_length=1, examples=[["상대 공급 최저 0.70배", "공급 압력 1위"]]
    )
    case_ids: list[str] = Field(default_factory=list, examples=[["case-01"]])


class ClosingInsight(BaseModel):
    """리포트 전체를 종합한 해석."""

    narrative: str = Field(min_length=1)
    focus_points: list[FocusPoint]
    watch_outs: list[str] = Field(
        examples=[["공급 확충이 방문 증가로 이어진다는 인과는 확인되지 않았습니다."]]
    )


class ReportSource(BaseModel):
    source_id: str = Field(min_length=1, examples=["src-02"])
    title: str = Field(min_length=1, examples=["삼척시 관광진흥 시행계획"])
    publisher: str = Field(min_length=1, examples=["삼척시"])
    url: HttpUrl = Field(examples=["https://www.samcheok.go.kr/"])
    published_at: str | None = Field(default=None, examples=["2025-03-01"])


class TourismGapReport(BaseModel):
    """관광 빈칸 종합 리포트."""

    report_version: str = Field(examples=["2026-09-08"])
    status: Literal["provisional", "final"] = Field(examples=["provisional"])
    target: RegionRef
    analysis_period: str = Field(pattern=r"^\d{6}~\d{6}$", examples=["202509~202608"])
    headline: str = Field(
        min_length=1,
        examples=["속초시는 우수 지역 세 곳 모두에서 체험관광 공급이 낮고, 수요 대비 공급 압력도 가장 높습니다."],
    )
    peers: PeerSection
    benchmarks: BenchmarkSection
    relative_supply: RelativeSupplySection
    supply_pressure: SupplyPressureSection
    gap_types: list[GapType]
    benchmark_cases: list[BenchmarkCase]
    closing_insight: ClosingInsight
    sources: list[ReportSource]
    limitations: list[str]
