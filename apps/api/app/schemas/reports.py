"""AI 관광 빈칸 리포트.

`config/ai/tourism_gap_report.schema.json`의 미러다. 두 곳이 어긋나면
리포트 생성기(`hankkeut_analysis.ai_reports`)의 검증을 통과한 payload가
API 경계에서 거부된다. 스키마를 고칠 때는 반드시 함께 고친다.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, HttpUrl

from .common import ContentType


class QuantitativeEvidence(BaseModel):
    metric: str = Field(min_length=1, examples=["체험관광 100㎢당 공급밀도"])
    target_value: float = Field(examples=[20.37])
    comparison: str = Field(min_length=1, examples=["포항시 31.44 대비 0.65배"])


class PeerCase(BaseModel):
    title: str = Field(min_length=1, examples=["포항 스페이스워크 야간 체험 프로그램"])
    peer_region: str = Field(min_length=1, examples=["포항시"])
    summary: str = Field(min_length=1, examples=["유휴 산업시설을 체험형 전망 콘텐츠로 전환한 사례"])
    source_ids: list[str] = Field(min_length=1, examples=[["src-01"]])


class GapType(BaseModel):
    content_type: ContentType = Field(examples=["체험관광"])
    judgement: str = Field(min_length=1, examples=["Peer 대비 체험관광 공급이 일관되게 낮다."])
    quantitative_evidence: list[QuantitativeEvidence] = Field(min_length=1)
    peer_cases: list[PeerCase]
    applicability_insight: str = Field(
        min_length=1, examples=["역사자원 밀집도가 높아 야간 체험 연계 여지가 있다."]
    )


class ReportSource(BaseModel):
    source_id: str = Field(min_length=1, examples=["src-01"])
    title: str = Field(min_length=1, examples=["포항시 관광진흥 시행계획"])
    publisher: str = Field(min_length=1, examples=["포항시"])
    url: HttpUrl = Field(examples=["https://www.pohang.go.kr/"])
    published_at: str | None = Field(default=None, examples=["2025-03-01"])


class TourismGapReport(BaseModel):
    """관광 빈칸 해석 리포트."""

    region_name: str = Field(min_length=1, examples=["경주시"])
    analysis_period: str = Field(pattern=r"^\d{6}~\d{6}$", examples=["202508~202607"])
    status: Literal["provisional", "final"] = Field(examples=["provisional"])
    gap_types: list[GapType]
    sources: list[ReportSource]
    limitations: list[str] = Field(
        examples=[["Peer는 구조적 유사 후보이며 관광 성과가 검증된 우수 Peer가 아닙니다."]]
    )
