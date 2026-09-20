import type { AdministrativeType } from './regions';

export type ReportStatus = 'FINAL' | 'PROVISIONAL' | 'UNKNOWN';

export type DiagnosisStatus =
  | 'GAP_FOUND'
  | 'NO_CLEAR_GAP'
  | 'INSUFFICIENT_DATA'
  | 'UNKNOWN';

export type TourismContentType =
  | 'EXPERIENCE_TOURISM'
  | 'ACCOMMODATION'
  | 'SHOPPING'
  | 'LEISURE_SPORTS'
  | 'CULTURE_TOURISM'
  | 'FOOD'
  | 'UNKNOWN';

export type GapSignalLevel =
  | 'STRONG_GAP_CANDIDATE'
  | 'NEEDS_REVIEW'
  | 'NO_CLEAR_GAP'
  | 'UNKNOWN';

export type OneLineReviewSource = 'LLM' | 'TEMPLATE' | 'UNKNOWN';
export type BenchmarkCaseType = 'FACILITY' | 'PROGRAM' | 'UNKNOWN';

export type KeyMetricCode =
  | 'MIN_BENCHMARK_SUPPLY_RATIO'
  | 'LOWER_BENCHMARK_COUNT'
  | 'SEARCHES_PER_PLACE'
  | 'SUPPLY_PLACE_COUNT'
  | 'SUPPLY_DENSITY_PER_100_KM2'
  | 'UNKNOWN';

export interface RegionReportResponseDto {
  report_version: string;
  report_status: ReportStatus;
  generated_at: string;
  target: RegionDto;
  analysis_period: AnalysisPeriodDto;
  summary: ReportSummaryDto;
  similar_regions: SimilarRegionDto[];
  tourism_type_comparisons: TourismTypeComparisonDto[];
  detailed_diagnoses: DetailedDiagnosisDto[];
  recommended_actions: RecommendedActionDto[];
  benchmark_cases: BenchmarkCaseDto[];
  methodology: MethodologyDto;
  sources: SourceDto[];
}

export interface RegionDto {
  region_id: string;
  province_name: string;
  region_name: string;
  administrative_type: AdministrativeType | 'UNKNOWN';
}

export interface AnalysisPeriodDto {
  start_ym: string;
  end_ym: string;
  month_count: number;
}

export interface PriorityContentTypeDto {
  rank: number;
  content_type: TourismContentType;
  signal_level: GapSignalLevel;
}

export interface ReportSummaryDto {
  diagnosis_status: DiagnosisStatus;
  primary_gap_type: TourismContentType | null;
  priority_content_types: PriorityContentTypeDto[];
  one_line_review: {
    text: string;
    source: OneLineReviewSource;
    generated_at: string | null;
  };
}

export interface SimilarRegionDto {
  region_id: string;
  province_name: string;
  region_name: string;
  administrative_type: AdministrativeType | 'UNKNOWN';
  rank: number;
  similarity: number;
}

export interface ComparisonRegionRefDto {
  region_id: string;
  region_name: string;
}

export interface RegionComparisonMetricDto {
  region_id: string;
  region_name: string;
  value: number | null;
}

export interface SupplyDensityComparisonDto {
  unit: 'PLACES_PER_100_KM2';
  target: RegionComparisonMetricDto;
  benchmarks: RegionComparisonMetricDto[];
  target_to_reference_ratio: number | null;
}

export interface SearchesPerPlaceComparisonDto {
  unit: 'SEARCHES_PER_PLACE';
  target: RegionComparisonMetricDto;
  benchmarks: RegionComparisonMetricDto[];
  target_to_reference_ratio: number | null;
}

export interface TourismTypeComparisonDto {
  content_type: TourismContentType;
  reference_region: ComparisonRegionRefDto | null;
  supply_density: SupplyDensityComparisonDto;
  searches_per_place: SearchesPerPlaceComparisonDto;
}

export interface DetailedDiagnosisDto {
  content_type: TourismContentType;
  signal_level: GapSignalLevel;
  judgement: string;
  insight: string;
  quantitative_evidence: QuantitativeEvidenceDto[];
  applicability_insight: string;
  case_ids: string[];
}

export interface QuantitativeEvidenceDto {
  metric_code: KeyMetricCode;
  value: number;
  comparisons: Array<{
    region_id: string;
    region_name: string;
    benchmark_value: number;
    target_to_benchmark_ratio: number | null;
  }>;
  rank: number | null;
  total_count: number | null;
}

export interface RecommendedActionDto {
  order: number;
  content_type: TourismContentType | null;
  title: string;
  rationale: string;
  evidence_texts: string[];
  case_ids: string[];
}

export interface BenchmarkCaseDto {
  case_id: string;
  benchmark_region_name: string;
  title: string;
  case_type: BenchmarkCaseType;
  content_type: TourismContentType;
  period: string;
  operator: string;
  summary: string;
  applicability: string;
  source_ids: string[];
}

export interface MethodologyDto {
  benchmark_selection_rule: string;
  benchmark_selection_note: string;
  supply_comparison_rule: string;
  search_pressure_definition: string;
  provisional_notice: string | null;
  limitations: string[];
}

export interface SourceDto {
  source_id: string;
  title: string;
  publisher: string;
  url: string;
  published_at: string;
}
