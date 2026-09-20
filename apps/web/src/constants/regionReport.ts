import type {
  BenchmarkCaseType,
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
