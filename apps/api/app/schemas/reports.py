"""지역 관광 보고서 화면 전용 응답.

프론트엔드가 숫자 계산이나 문자열 파싱 없이 표시와 포맷팅만 하도록, 판정과
수치는 모두 백엔드가 확정해 구조화된 값으로 내린다. 그래서 이 스키마에는
가공한 표시 문자열(`"0.70배"` 같은 것)이 없다. 반올림하지 않은 원본 숫자를
내리고 표시 반올림은 프론트엔드가 한다.

계산되지 않은 값은 `null`이다. 0으로 채우면 '자료 없음'이 '공급 없음'이 되어
순위가 뒤집힌다.
"""

from __future__ import annotations

from enum import Enum
from typing import Annotated, Literal

from pydantic import BaseModel, Field, HttpUrl, model_validator

from .common import AdministrativeType, ContentType, RegionRef


class ReportStatus(str, Enum):
    FINAL = "FINAL"
    PROVISIONAL = "PROVISIONAL"


class DiagnosisStatus(str, Enum):
    """분석 상태는 HTTP 오류와 분리한다. 데이터가 부족한 지역도 200이다."""

    GAP_FOUND = "GAP_FOUND"
    NO_CLEAR_GAP = "NO_CLEAR_GAP"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


class GapSignalLevel(str, Enum):
    STRONG_GAP_CANDIDATE = "STRONG_GAP_CANDIDATE"
    NEEDS_REVIEW = "NEEDS_REVIEW"
    NO_CLEAR_GAP = "NO_CLEAR_GAP"


class OneLineReviewSource(str, Enum):
    LLM = "LLM"
    TEMPLATE = "TEMPLATE"


class BenchmarkCaseType(str, Enum):
    FACILITY = "FACILITY"
    PROGRAM = "PROGRAM"


class KeyMetricCode(str, Enum):
    MIN_BENCHMARK_SUPPLY_RATIO = "MIN_BENCHMARK_SUPPLY_RATIO"
    LOWER_BENCHMARK_COUNT = "LOWER_BENCHMARK_COUNT"
    SEARCHES_PER_PLACE = "SEARCHES_PER_PLACE"
    SUPPLY_PLACE_COUNT = "SUPPLY_PLACE_COUNT"
    SUPPLY_DENSITY_PER_100_KM2 = "SUPPLY_DENSITY_PER_100_KM2"


class AnalysisPeriod(BaseModel):
    start_ym: str = Field(pattern=r"^\d{6}$", examples=["202509"])
    end_ym: str = Field(pattern=r"^\d{6}$", examples=["202608"])
    month_count: int = Field(ge=1, examples=[12])


# ---------------------------------------------------------------------------
# 핵심 지표 — metric_code로 구분하는 판별 유니온
# ---------------------------------------------------------------------------
class MinBenchmarkSupplyRatioMetric(BaseModel):
    """비교 기준 지역 대비 가장 낮은 공급 비율.

    기준은 100㎢당 공급밀도 비율이다. 구성비와 밀도를 섞어 최솟값을 내면
    무엇의 몇 배인지 알 수 없는 숫자가 되므로 한 가지 기준으로 고정한다.
    """

    metric_code: Literal[KeyMetricCode.MIN_BENCHMARK_SUPPLY_RATIO]
    content_type: ContentType
    value: float = Field(examples=[0.6959])
    benchmark_region_id: str = Field(pattern=r"^\d{5}$", examples=["47110"])
    benchmark_region_name: str = Field(examples=["포항시"])


class LowerBenchmarkCountMetric(BaseModel):
    metric_code: Literal[KeyMetricCode.LOWER_BENCHMARK_COUNT]
    content_type: ContentType
    value: int = Field(ge=0, examples=[2])
    total_benchmark_count: int = Field(ge=0, examples=[2])


class SearchesPerPlaceMetric(BaseModel):
    metric_code: Literal[KeyMetricCode.SEARCHES_PER_PLACE]
    content_type: ContentType
    value: float = Field(examples=[2117.5862])
    rank: int = Field(ge=1, examples=[1])
    total_content_type_count: int = Field(ge=1, examples=[6])


class SupplyPlaceCountMetric(BaseModel):
    metric_code: Literal[KeyMetricCode.SUPPLY_PLACE_COUNT]
    content_type: ContentType
    value: float = Field(examples=[87])


class SupplyDensityMetric(BaseModel):
    metric_code: Literal[KeyMetricCode.SUPPLY_DENSITY_PER_100_KM2]
    content_type: ContentType
    value: float = Field(examples=[6.569])


KeyMetric = Annotated[
    MinBenchmarkSupplyRatioMetric
    | LowerBenchmarkCountMetric
    | SearchesPerPlaceMetric
    | SupplyPlaceCountMetric
    | SupplyDensityMetric,
    Field(discriminator="metric_code"),
]


class OneLineReview(BaseModel):
    """사용자용 한 문장. 핵심 수치 카드와 역할이 다르므로 둘 다 내린다."""

    text: str = Field(min_length=1)
    source: OneLineReviewSource
    generated_at: str | None = Field(default=None)


class PriorityContentType(BaseModel):
    rank: int = Field(ge=1, le=3)
    content_type: ContentType
    signal_level: GapSignalLevel


class ReportSummary(BaseModel):
    diagnosis_status: DiagnosisStatus
    primary_gap_type: ContentType | None = Field(default=None)
    priority_content_types: list[PriorityContentType] = Field(default_factory=list, max_length=3)
    one_line_review: OneLineReview
    key_metrics: list[KeyMetric] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_summary_consistency(self) -> "ReportSummary":
        codes = [metric.metric_code for metric in self.key_metrics]
        if len(codes) != len(set(codes)):
            raise ValueError("key_metrics의 metric_code는 중복될 수 없습니다.")
        if self.diagnosis_status is DiagnosisStatus.INSUFFICIENT_DATA:
            if self.primary_gap_type is not None:
                raise ValueError("INSUFFICIENT_DATA에서는 primary_gap_type이 null이어야 합니다.")
            if self.key_metrics:
                raise ValueError("INSUFFICIENT_DATA에서는 key_metrics가 빈 배열이어야 합니다.")
            if self.priority_content_types:
                raise ValueError("INSUFFICIENT_DATA에서는 priority_content_types가 빈 배열이어야 합니다.")
            return self
        if self.diagnosis_status is DiagnosisStatus.GAP_FOUND and self.primary_gap_type is None:
            raise ValueError("GAP_FOUND에서는 primary_gap_type이 있어야 합니다.")
        ranks = [item.rank for item in self.priority_content_types]
        if ranks != list(range(1, len(ranks) + 1)):
            raise ValueError("priority_content_types의 rank는 1부터 중복 없이 연속되어야 합니다.")
        if self.diagnosis_status is DiagnosisStatus.GAP_FOUND and (
            not self.priority_content_types
            or self.priority_content_types[0].content_type is not self.primary_gap_type
        ):
            raise ValueError("GAP_FOUND의 priority_content_types 1위는 primary_gap_type과 같아야 합니다.")
        if self.diagnosis_status is DiagnosisStatus.NO_CLEAR_GAP and self.primary_gap_type is not None:
            raise ValueError("NO_CLEAR_GAP에서는 primary_gap_type이 null이어야 합니다.")
        if not 2 <= len(self.key_metrics) <= 4:
            raise ValueError("정상 분석 결과의 key_metrics는 2~4개여야 합니다.")
        return self


# ---------------------------------------------------------------------------
# 근거
# ---------------------------------------------------------------------------
class RegionMetric(BaseModel):
    region_id: str = Field(pattern=r"^\d{5}$", examples=["47110"])
    region_name: str = Field(examples=["포항시"])
    value: float = Field(examples=[9.4685])
    target_to_benchmark_ratio: float | None = Field(default=None, examples=[0.6938])


class SupplyDensityEvidence(BaseModel):
    # 심화 산출물을 준비하는 동안 프론트 계약을 유지하는 보고서 전용 표시다.
    # 공용 ContentType에 넣으면 실제 분석 반복에 UNKNOWN이 섞이므로 여기에서만 허용한다.
    content_type: ContentType | Literal["UNKNOWN"]
    target: RegionMetric
    benchmarks: list[RegionMetric] = Field(default_factory=list)


class ContentTypeSearchMetric(BaseModel):
    content_type: ContentType
    navigation_search_count: int = Field(ge=0, examples=[184230])
    supply_place_count: int = Field(ge=0, examples=[87])
    searches_per_place: float = Field(examples=[2117.5862])
    rank: int = Field(ge=1, examples=[1], description="장소당 검색량 내림차순 순위")


class SearchesPerPlaceEvidence(BaseModel):
    metric_definition: str = Field(
        examples=["유형별 내비게이션 목적지 검색량 ÷ 카카오맵 유형별 장소 수"]
    )
    items: list[ContentTypeSearchMetric] = Field(default_factory=list)


class ReportEvidence(BaseModel):
    supply_density: SupplyDensityEvidence
    searches_per_place: SearchesPerPlaceEvidence


class SimilarRegion(BaseModel):
    region_id: str = Field(pattern=r"^\d{5}$")
    province_name: str
    region_name: str
    administrative_type: AdministrativeType
    rank: int = Field(ge=1)
    similarity: float = Field(ge=0, le=1)


class ComparisonRegionRef(BaseModel):
    region_id: str = Field(pattern=r"^\d{5}$")
    region_name: str


class RegionComparisonMetric(BaseModel):
    region_id: str = Field(pattern=r"^\d{5}$")
    region_name: str
    value: float | None = None


class SupplyDensityComparison(BaseModel):
    unit: Literal["PLACES_PER_100_KM2"]
    target: RegionComparisonMetric
    benchmarks: list[RegionComparisonMetric] = Field(default_factory=list)
    target_to_reference_ratio: float | None = None


class SearchesPerPlaceComparison(BaseModel):
    unit: Literal["SEARCHES_PER_PLACE"]
    target: RegionComparisonMetric
    benchmarks: list[RegionComparisonMetric] = Field(default_factory=list)
    target_to_reference_ratio: float | None = None


class TourismTypeComparison(BaseModel):
    content_type: ContentType
    reference_region: ComparisonRegionRef | None = None
    supply_density: SupplyDensityComparison
    searches_per_place: SearchesPerPlaceComparison


# ---------------------------------------------------------------------------
# 유형별 개요와 상세 진단
# ---------------------------------------------------------------------------
class CategoryOverviewItem(BaseModel):
    content_type: ContentType
    signal_level: GapSignalLevel
    supply_place_count: int = Field(examples=[87])
    composition_share: float = Field(examples=[0.069])
    supply_density_per_100_km2: float = Field(examples=[6.569])
    lower_benchmark_count: int = Field(ge=0, examples=[2])
    total_benchmark_count: int = Field(ge=0, examples=[2])
    lowest_benchmark_supply_ratio: float | None = Field(default=None, examples=[0.6938])
    searches_per_place: float = Field(examples=[2117.5862])
    search_rank: int = Field(ge=1, examples=[1])


class BenchmarkComparison(BaseModel):
    region_id: str = Field(pattern=r"^\d{5}$", examples=["47110"])
    region_name: str = Field(examples=["포항시"])
    benchmark_value: float = Field(examples=[9.4685])
    target_to_benchmark_ratio: float | None = Field(default=None, examples=[0.6938])


class QuantitativeEvidence(BaseModel):
    metric_code: KeyMetricCode
    value: float = Field(examples=[6.569])
    comparisons: list[BenchmarkComparison] = Field(default_factory=list)
    rank: int | None = Field(default=None, ge=1)
    total_count: int | None = Field(default=None, ge=1)


class DetailedDiagnosis(BaseModel):
    content_type: ContentType
    signal_level: Literal[
        GapSignalLevel.STRONG_GAP_CANDIDATE, GapSignalLevel.NEEDS_REVIEW
    ]
    judgement: str = Field(min_length=1)
    insight: str = Field(min_length=1)
    quantitative_evidence: list[QuantitativeEvidence] = Field(default_factory=list)
    applicability_insight: str = Field(min_length=1)
    case_ids: list[str] = Field(default_factory=list, examples=[["case-01"]])


class RecommendedAction(BaseModel):
    order: int = Field(ge=1, examples=[1])
    content_type: ContentType | None = Field(default=None)
    title: str = Field(min_length=1)
    rationale: str = Field(min_length=1)
    evidence_texts: list[str] = Field(default_factory=list)
    case_ids: list[str] = Field(default_factory=list)


class BenchmarkCase(BaseModel):
    """비교 기준 지역에서 실제로 추진된 관광 사업·프로그램."""

    case_id: str = Field(min_length=1, examples=["case-01"])
    benchmark_region_name: str = Field(min_length=1, examples=["포항시"])
    title: str = Field(min_length=1, examples=["포항 스페이스워크"])
    case_type: BenchmarkCaseType
    content_type: ContentType
    period: str = Field(min_length=1, examples=["2021"])
    operator: str = Field(min_length=1, examples=["포항시"])
    summary: str = Field(min_length=1)
    applicability: str = Field(min_length=1)
    source_ids: list[str] = Field(default_factory=list, examples=[["source-1"]])


class Methodology(BaseModel):
    benchmark_selection_rule: str = Field(min_length=1)
    benchmark_selection_note: str = Field(min_length=1)
    supply_comparison_rule: str = Field(min_length=1)
    search_pressure_definition: str = Field(min_length=1)
    #: PROVISIONAL일 때만 값이 있다. FINAL이면 null.
    provisional_notice: str | None = Field(default=None)
    limitations: list[str] = Field(default_factory=list)


class ReportSource(BaseModel):
    source_id: str = Field(min_length=1, examples=["source-1"])
    title: str = Field(min_length=1)
    publisher: str = Field(min_length=1)
    url: HttpUrl = Field(examples=["https://www.seosan.go.kr/"])
    #: 실제 값이 "상시 갱신", "2021-11-18 외" 같은 자유 문자열이라 날짜로
    #: 강제하지 않는다.
    published_at: str = Field(min_length=1, examples=["2024"])


class RegionReport(BaseModel):
    """지역 관광 보고서 화면 전용 응답."""

    report_version: str = Field(examples=["1.0.0+2026-09-13"])
    report_status: ReportStatus
    generated_at: str = Field(examples=["2026-09-13T02:00:00+00:00"])
    target: RegionRef
    analysis_period: AnalysisPeriod
    summary: ReportSummary
    similar_regions: list[SimilarRegion] = Field(default_factory=list)
    tourism_type_comparisons: list[TourismTypeComparison] = Field(default_factory=list)
    evidence: ReportEvidence
    category_overview: list[CategoryOverviewItem] = Field(default_factory=list)
    detailed_diagnoses: list[DetailedDiagnosis] = Field(default_factory=list)
    recommended_actions: list[RecommendedAction] = Field(default_factory=list)
    benchmark_cases: list[BenchmarkCase] = Field(default_factory=list)
    methodology: Methodology
    sources: list[ReportSource] = Field(default_factory=list)
