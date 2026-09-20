import { Info } from 'lucide-react';
import { useState } from 'react';
import {
  TOURISM_CONTENT_LABEL,
  TOURISM_CONTENT_ORDER,
} from '../../constants/regionReport';
import type {
  RegionComparisonMetricDto,
  TourismContentType,
  TourismTypeComparisonDto,
} from '../../types/regionReport';
import { cn } from '../../utils/cn';
import {
  formatCount,
  formatDecimal,
  formatRatio,
  getNormalizedBarWidth,
} from '../../utils/regionReport';
import { Button } from '../ui/button';
import { Popover, PopoverContent, PopoverTrigger } from '../ui/popover';

// 탭에는 UNKNOWN을 제외한 6개 관광 콘텐츠 유형만 노출한다.
const SELECTABLE_TYPES = TOURISM_CONTENT_ORDER.filter(
  (type) => type !== 'UNKNOWN'
);

interface TourismTypeComparisonSectionProps {
  comparisons: TourismTypeComparisonDto[];
  primaryGapType: TourismContentType | null;
  // 공급밀도·공급 압력 지표 설명은 방법론 카드와 같은 문구를 그대로 써서
  // 화면 전체에서 같은 지표를 다르게 설명하지 않게 한다.
  supplyDensityDefinition: string;
  searchPressureDefinition: string;
}

function TourismTypeComparisonSection({
  comparisons,
  primaryGapType,
  supplyDensityDefinition,
  searchPressureDefinition,
}: TourismTypeComparisonSectionProps) {
  const comparisonByType = new Map(
    comparisons.map((comparison) => [comparison.content_type, comparison])
  );
  const availableTypes = SELECTABLE_TYPES.filter((type) =>
    comparisonByType.has(type)
  );
  const [selectedType, setSelectedType] = useState<TourismContentType | null>(
    () =>
      primaryGapType && comparisonByType.has(primaryGapType)
        ? primaryGapType
        : (availableTypes[0] ?? null)
  );

  if (availableTypes.length === 0) return null;

  const activeType =
    selectedType && comparisonByType.has(selectedType)
      ? selectedType
      : availableTypes[0];
  const active = comparisonByType.get(activeType);
  if (!active) return null;

  const referenceName = active.reference_region?.region_name ?? null;
  const densityRows = [
    active.supply_density.target,
    ...active.supply_density.benchmarks,
  ];
  const searchRows = [
    active.searches_per_place.target,
    ...active.searches_per_place.benchmarks,
  ];

  return (
    <section className="bg-muted/70">
      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-4 px-4 py-6 sm:px-8 lg:px-12">
        <div>
          <h2>관광 콘텐츠 유형별 공급 현황</h2>
          <p className="mt-1 text-body-small text-muted-foreground">
            관광 콘텐츠 유형별 공급밀도와 공급 압력을 유사 지역과 비교합니다.
          </p>
        </div>

        <div
          role="tablist"
          aria-label="관광 콘텐츠 유형"
          className="flex flex-wrap gap-2 rounded-xl border bg-card p-1"
        >
          {availableTypes.map((type) => (
            <button
              key={type}
              type="button"
              role="tab"
              aria-selected={type === activeType}
              onClick={() => setSelectedType(type)}
              className={cn(
                'h-9 min-w-28 flex-1 rounded-lg text-label-small transition-colors',
                type === activeType
                  ? 'bg-primary text-primary-foreground'
                  : 'bg-transparent text-foreground hover:bg-muted'
              )}
            >
              {TOURISM_CONTENT_LABEL[type]}
            </button>
          ))}
        </div>

        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <article className="flex flex-col gap-1.5 rounded-xl border bg-card px-4.5 py-4">
            <p className="flex items-center gap-1 text-body-small text-primary">
              {referenceName
                ? `${referenceName} 대비 공급밀도`
                : '비교 기준 지역 없음'}
              <MetricInfoIcon
                label="공급밀도"
                description={supplyDensityDefinition}
              />
            </p>
            <p className="text-heading text-primary">
              {formatRatio(active.supply_density.target_to_reference_ratio)}
            </p>
          </article>
          <article className="flex flex-col gap-1.5 rounded-xl border bg-card px-4.5 py-4">
            <p className="flex items-center gap-1 text-body-small text-primary">
              {referenceName
                ? `${referenceName} 대비 공급 압력`
                : '비교 기준 지역 없음'}
              <MetricInfoIcon
                label="공급 압력"
                description={searchPressureDefinition}
              />
            </p>
            <p className="text-heading text-primary">
              {formatRatio(active.searches_per_place.target_to_reference_ratio)}
            </p>
          </article>
        </div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <ComparisonChartCard
            title={`${TOURISM_CONTENT_LABEL[activeType]} 공급밀도`}
            unitLabel="100㎢당 등록 장소 수"
            rows={densityRows}
            formatValue={formatDecimal}
            infoLabel="공급밀도"
            infoDescription={supplyDensityDefinition}
          />
          <ComparisonChartCard
            title={`${TOURISM_CONTENT_LABEL[activeType]} 공급 압력`}
            unitLabel="등록 장소 1곳당 최근 12개월 목적지 검색량"
            rows={searchRows}
            formatValue={(value) => `${formatCount(value)}회`}
            infoLabel="공급 압력"
            infoDescription={searchPressureDefinition}
          />
        </div>
      </div>
    </section>
  );
}

interface ComparisonChartCardProps {
  title: string;
  unitLabel: string;
  rows: RegionComparisonMetricDto[];
  formatValue: (value: number) => string;
  infoLabel: string;
  infoDescription: string;
}

function ComparisonChartCard({
  title,
  unitLabel,
  rows,
  formatValue,
  infoLabel,
  infoDescription,
}: ComparisonChartCardProps) {
  const numericValues = rows
    .map((row) => row.value)
    .filter((value): value is number => value !== null);

  return (
    <article className="flex flex-col gap-3 rounded-xl border bg-card p-5">
      <div>
        <p className="flex items-center gap-1 text-body-strong">
          {title}
          <MetricInfoIcon label={infoLabel} description={infoDescription} />
        </p>
        <p className="text-body-small text-muted-foreground">{unitLabel}</p>
      </div>
      <div className="flex flex-col gap-2 py-1">
        {rows.map((row, index) => (
          <div
            key={row.region_id}
            className="grid grid-cols-[minmax(3.5rem,auto)_minmax(6rem,1fr)_auto] items-center gap-2.5 text-body-small"
          >
            <span className={index === 0 ? 'text-primary' : 'text-foreground'}>
              {row.region_name}
            </span>
            <span className="h-2.5 overflow-hidden rounded-full bg-border/50">
              {row.value !== null && (
                <span
                  className={
                    index === 0
                      ? 'block h-full rounded-full bg-primary'
                      : 'block h-full rounded-full bg-muted-foreground/65'
                  }
                  style={{
                    width: `${getNormalizedBarWidth(row.value, numericValues)}%`,
                  }}
                />
              )}
            </span>
            <span className={index === 0 ? 'text-primary' : ''}>
              {row.value === null ? '—' : formatValue(row.value)}
            </span>
          </div>
        ))}
      </div>
    </article>
  );
}

interface MetricInfoIconProps {
  label: string;
  description: string;
}

function MetricInfoIcon({ label, description }: MetricInfoIconProps) {
  return (
    <Popover>
      <PopoverTrigger asChild>
        <Button
          type="button"
          variant="ghost"
          size="icon-xs"
          aria-label={`${label} 설명 보기`}
          className="size-4.5 shrink-0 text-muted-foreground hover:bg-transparent hover:text-foreground"
        >
          <Info aria-hidden="true" className="size-3.5" strokeWidth={1.75} />
        </Button>
      </PopoverTrigger>
      <PopoverContent>{description}</PopoverContent>
    </Popover>
  );
}

export default TourismTypeComparisonSection;
