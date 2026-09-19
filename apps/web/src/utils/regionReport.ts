import { TOURISM_CONTENT_ORDER } from '../constants/regionReport';
import type {
  CategoryOverviewItemDto,
  ContentTypeSearchMetricDto,
  RecommendedActionDto,
  SourceDto,
  TourismContentType,
} from '../types/regionReport';

const countFormatter = new Intl.NumberFormat('ko-KR', {
  maximumFractionDigits: 0,
});

const decimalFormatter = new Intl.NumberFormat('ko-KR', {
  maximumFractionDigits: 2,
});

export const formatCount = (value: number) => countFormatter.format(value);

export const formatDecimal = (value: number) => decimalFormatter.format(value);

export const formatRatio = (value: number | null) =>
  value === null ? '-' : `${value.toFixed(2)}배`;

export const formatTwoDigitOrder = (value: number) =>
  String(value).padStart(2, '0');

const formatYearMonth = (value: string) => {
  if (!/^\d{6}$/.test(value)) return null;
  const month = Number(value.slice(4));
  if (month < 1 || month > 12) return null;
  return `${value.slice(0, 4)}.${value.slice(4)}`;
};

export const formatYearMonthRange = (start: string, end: string) => {
  const formattedStart = formatYearMonth(start);
  const formattedEnd = formatYearMonth(end);
  if (formattedStart === null || formattedEnd === null) return '—';
  return `${formattedStart}–${formattedEnd}`;
};

export const getNormalizedBarWidth = (value: number, values: number[]) => {
  const maximum = Math.max(0, ...values);
  if (maximum === 0 || value <= 0) return 0;
  return Math.min(100, (value / maximum) * 100);
};

export const sortSearchMetrics = (items: ContentTypeSearchMetricDto[]) =>
  [...items].sort((left, right) => left.rank - right.rank);

export const sortRecommendedActions = (items: RecommendedActionDto[]) =>
  [...items].sort((left, right) => left.order - right.order);

export const sortCategoryOverview = (
  items: CategoryOverviewItemDto[],
  primaryGapType: TourismContentType | null
) => {
  const order = new Map(
    TOURISM_CONTENT_ORDER.map((contentType, index) => [contentType, index])
  );
  return [...items].sort((left, right) => {
    if (left.content_type === primaryGapType) return -1;
    if (right.content_type === primaryGapType) return 1;
    return (
      (order.get(left.content_type) ?? Number.MAX_SAFE_INTEGER) -
      (order.get(right.content_type) ?? Number.MAX_SAFE_INTEGER)
    );
  });
};

export const resolveSources = (sourceIds: string[], sources: SourceDto[]) => {
  const sourceById = new Map(
    sources.map((source) => [source.source_id, source])
  );
  return sourceIds.flatMap((sourceId) => {
    const source = sourceById.get(sourceId);
    return source ? [source] : [];
  });
};
