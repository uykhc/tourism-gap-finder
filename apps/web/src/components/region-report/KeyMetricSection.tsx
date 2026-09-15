import {
  KEY_METRIC_TITLE,
  TOURISM_CONTENT_LABEL,
} from '../../constants/regionReport';
import type { KeyMetricDto } from '../../types/regionReport';
import {
  formatCount,
  formatDecimal,
  formatRatio,
} from '../../utils/regionReport';

interface MetricDisplay {
  value: string;
  description: string;
}

const getMetricDisplay = (metric: KeyMetricDto): MetricDisplay => {
  switch (metric.metric_code) {
    case 'MIN_BENCHMARK_SUPPLY_RATIO':
      return {
        value: formatRatio(metric.value),
        description: `${metric.benchmark_region_name} 대비 최저`,
      };
    case 'LOWER_BENCHMARK_COUNT':
      return {
        value:
          metric.value === metric.total_benchmark_count
            ? `${formatCount(metric.value)}곳 모두`
            : `${formatCount(metric.value)}곳`,
        description: `우수 지역 ${formatCount(metric.total_benchmark_count)}곳보다 낮음`,
      };
    case 'SEARCHES_PER_PLACE':
      return {
        value: `${formatCount(metric.value)}회`,
        description: `장소당 검색량 · ${metric.total_content_type_count}개 유형 중 ${metric.rank}위`,
      };
    case 'SUPPLY_PLACE_COUNT':
      return {
        value: `${formatCount(metric.value)}개`,
        description: `${TOURISM_CONTENT_LABEL[metric.content_type]} 등록 장소`,
      };
    case 'SUPPLY_DENSITY_PER_100_KM2':
      return {
        value: formatDecimal(metric.value),
        description: '100㎢당 등록 장소 수',
      };
    case 'UNKNOWN':
      return {
        value: formatDecimal(metric.value),
        description: TOURISM_CONTENT_LABEL[metric.content_type],
      };
  }
};

interface KeyMetricSectionProps {
  metrics: KeyMetricDto[];
}

function KeyMetricSection({ metrics }: KeyMetricSectionProps) {
  if (metrics.length === 0) return null;

  return (
    <section className="bg-background">
      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-4 px-4 py-6 sm:px-8 lg:px-12">
        <h2>핵심 진단</h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
          {metrics.map((metric, index) => {
            const display = getMetricDisplay(metric);
            return (
              <article
                key={`${metric.metric_code}-${index}`}
                className="flex min-h-26 flex-col gap-1.5 rounded-xl border bg-card px-4.5 py-4"
              >
                <p className="text-body-small text-muted-foreground">
                  {KEY_METRIC_TITLE[metric.metric_code]}
                </p>
                <p className="text-heading text-primary">{display.value}</p>
                <p className="text-body-small text-muted-foreground">
                  {display.description}
                </p>
              </article>
            );
          })}
        </div>
      </div>
    </section>
  );
}

export default KeyMetricSection;
