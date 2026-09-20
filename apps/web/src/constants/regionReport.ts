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

// 유형별 공급 현황 섹션의 정보 아이콘 설명. 방법론 카드의 산출 규칙
// 문구와 달리, 수치를 어떻게 해석해야 하는지에 집중한 설명이다.
export const SUPPLY_DENSITY_DESCRIPTION =
  '지역 면적 100㎢당 등록된 해당 유형의 장소 수입니다. 이 값이 낮을수록 같은 면적에 이용할 수 있는 장소가 적다는 뜻입니다.';

export const SEARCH_PRESSURE_DESCRIPTION =
  '최근 12개월 동안 해당 유형 장소 1곳당 발생한 내비게이션 목적지 검색량입니다. 이 값이 높을수록 장소 수에 비해 수요가 많아, 공급이 부족할 가능성이 크다는 뜻입니다.';
