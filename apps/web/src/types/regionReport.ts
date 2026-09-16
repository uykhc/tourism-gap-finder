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
  evidence: ReportEvidenceDto;
  category_overview: CategoryOverviewItemDto[];
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
  administrative_type: '시' | '군' | '구' | 'UNKNOWN';
}

export interface AnalysisPeriodDto {
  start_ym: string;
  end_ym: string;
  month_count: number;
}

export interface ReportSummaryDto {
  diagnosis_status: DiagnosisStatus;
  primary_gap_type: TourismContentType | null;
  one_line_review: {
    text: string;
    source: OneLineReviewSource;
    generated_at: string | null;
  };
  key_metrics: KeyMetricDto[];
}

interface KeyMetricBaseDto {
  content_type: TourismContentType;
  value: number;
}

export interface MinimumBenchmarkSupplyRatioMetricDto extends KeyMetricBaseDto {
  metric_code: 'MIN_BENCHMARK_SUPPLY_RATIO';
  benchmark_region_id: string;
  benchmark_region_name: string;
}

export interface LowerBenchmarkCountMetricDto extends KeyMetricBaseDto {
  metric_code: 'LOWER_BENCHMARK_COUNT';
  total_benchmark_count: number;
}

export interface SearchesPerPlaceMetricDto extends KeyMetricBaseDto {
  metric_code: 'SEARCHES_PER_PLACE';
  rank: number;
  total_content_type_count: number;
}

export interface SupplyPlaceCountMetricDto extends KeyMetricBaseDto {
  metric_code: 'SUPPLY_PLACE_COUNT';
}

export interface SupplyDensityMetricDto extends KeyMetricBaseDto {
  metric_code: 'SUPPLY_DENSITY_PER_100_KM2';
}

export interface UnknownKeyMetricDto extends KeyMetricBaseDto {
  metric_code: 'UNKNOWN';
}

export type KeyMetricDto =
  | MinimumBenchmarkSupplyRatioMetricDto
  | LowerBenchmarkCountMetricDto
  | SearchesPerPlaceMetricDto
  | SupplyPlaceCountMetricDto
  | SupplyDensityMetricDto
  | UnknownKeyMetricDto;

export interface ReportEvidenceDto {
  supply_density: {
    content_type: TourismContentType;
    target: RegionMetricDto;
    benchmarks: RegionMetricDto[];
  };
  searches_per_place: {
    metric_definition: string;
    items: ContentTypeSearchMetricDto[];
  };
}

export interface RegionMetricDto {
  region_id: string;
  region_name: string;
  value: number;
  target_to_benchmark_ratio?: number;
}

export interface ContentTypeSearchMetricDto {
  content_type: TourismContentType;
  navigation_search_count: number;
  supply_place_count: number;
  searches_per_place: number;
  rank: number;
}

export interface CategoryOverviewItemDto {
  content_type: TourismContentType;
  signal_level: GapSignalLevel;
  supply_place_count: number;
  composition_share: number;
  supply_density_per_100_km2: number;
  lower_benchmark_count: number;
  total_benchmark_count: number;
  lowest_benchmark_supply_ratio: number | null;
  searches_per_place: number;
  search_rank: number;
}

export interface DetailedDiagnosisDto {
  content_type: TourismContentType;
  signal_level: GapSignalLevel;
  judgement: string;
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
    target_to_benchmark_ratio: number;
  }>;
  rank?: number;
  total_count?: number;
}

export interface RecommendedActionDto {
  order: number;
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
