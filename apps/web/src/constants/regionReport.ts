import type {
  BenchmarkCaseType,
  GapSignalLevel,
  KeyMetricCode,
  TourismContentType,
} from '../types/regionReport';

export const TOURISM_CONTENT_LABEL: Record<TourismContentType, string> = {
  EXPERIENCE_TOURISM: '체험관광',
  ACCOMMODATION: '숙박',
  SHOPPING: '쇼핑',
  LEISURE_SPORTS: '레저스포츠',
  CULTURE_TOURISM: '문화관광',
  FOOD: '음식',
  UNKNOWN: '알 수 없는 유형',
};

export const TOURISM_CONTENT_ORDER: TourismContentType[] = [
  'EXPERIENCE_TOURISM',
  'SHOPPING',
  'ACCOMMODATION',
  'LEISURE_SPORTS',
  'CULTURE_TOURISM',
  'FOOD',
  'UNKNOWN',
];

export const CASE_TYPE_LABEL: Record<BenchmarkCaseType, string> = {
  FACILITY: '시설',
  PROGRAM: '프로그램',
  UNKNOWN: '유형 미상',
};

export const SIGNAL_LEVEL_LABEL: Record<GapSignalLevel, string> = {
  STRONG_GAP_CANDIDATE: '우선 검증',
  NEEDS_REVIEW: '추가 확인',
  NO_CLEAR_GAP: '상대적 부족 아님',
  UNKNOWN: '확인 필요',
};

export const DETAIL_SIGNAL_LABEL: Record<GapSignalLevel, string> = {
  STRONG_GAP_CANDIDATE: '강한 빈칸 후보',
  NEEDS_REVIEW: '추가 확인 필요',
  NO_CLEAR_GAP: '상대적 부족 아님',
  UNKNOWN: '확인 필요',
};

export const KEY_METRIC_TITLE: Record<KeyMetricCode, string> = {
  MIN_BENCHMARK_SUPPLY_RATIO: '상대 공급',
  LOWER_BENCHMARK_COUNT: '비교 일관성',
  SEARCHES_PER_PLACE: '수요 압력',
  SUPPLY_PLACE_COUNT: '등록 공급',
  SUPPLY_DENSITY_PER_100_KM2: '공급밀도',
  UNKNOWN: '추가 지표',
};
