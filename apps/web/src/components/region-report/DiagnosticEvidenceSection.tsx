import { TOURISM_CONTENT_LABEL } from '../../constants/regionReport';
import type {
  KeyMetricDto,
  ReportEvidenceDto,
  TourismContentType,
} from '../../types/regionReport';
import {
  formatCount,
  formatDecimal,
  formatRatio,
  getNormalizedBarWidth,
  sortSearchMetrics,
} from '../../utils/regionReport';

interface DiagnosticEvidenceSectionProps {
  evidence: ReportEvidenceDto;
  primaryGapType: TourismContentType;
  keyMetrics: KeyMetricDto[];
  searchPressureDefinition: string;
}

function DiagnosticEvidenceSection({
  evidence,
  primaryGapType,
  keyMetrics,
  searchPressureDefinition,
}: DiagnosticEvidenceSectionProps) {
  const densityRows = [
    evidence.supply_density.target,
    ...evidence.supply_density.benchmarks,
  ];
  const densityValues = densityRows.map((row) => row.value);
  const searchRows = sortSearchMetrics(evidence.searches_per_place.items);
  const searchValues = searchRows.map((row) => row.searches_per_place);
  const lowerCount = keyMetrics.find(
    (metric) => metric.metric_code === 'LOWER_BENCHMARK_COUNT'
  );
  const minimumRatio = keyMetrics.find(
    (metric) => metric.metric_code === 'MIN_BENCHMARK_SUPPLY_RATIO'
  );

  return (
    <section className="bg-card">
      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-3.5 px-4 py-7 sm:px-8 lg:px-12">
        <h2>왜 {TOURISM_CONTENT_LABEL[primaryGapType]}인가</h2>
        <p className="text-body-small text-muted-foreground">
          상대 공급과 장소당 검색량이 같은 방향을 가리키는지 함께 확인합니다.
        </p>
        <div className="grid grid-cols-1 gap-4 pt-0.5 lg:grid-cols-2">
          <article className="flex flex-col gap-3 rounded-xl border bg-card p-5">
            <div>
              <p className="text-body-strong">
                {TOURISM_CONTENT_LABEL[evidence.supply_density.content_type]}{' '}
                공급밀도
              </p>
              <p className="text-body-small text-muted-foreground">
                100㎢당 등록 장소 수
              </p>
            </div>
            <div className="flex flex-col gap-2 py-1">
              {densityRows.map((row, index) => (
                <div
                  key={row.region_id}
                  className="grid grid-cols-[minmax(3.5rem,auto)_minmax(6rem,1fr)_auto] items-center gap-2.5 text-body-small"
                >
                  <span
                    className={index === 0 ? 'text-primary' : 'text-foreground'}
                  >
                    {row.region_name}
                  </span>
                  <span className="h-2.5 overflow-hidden rounded-full bg-border/50">
                    <span
                      className={
                        index === 0
                          ? 'block h-full rounded-full bg-primary'
                          : 'block h-full rounded-full bg-muted-foreground/65'
                      }
                      style={{
                        width: `${getNormalizedBarWidth(row.value, densityValues)}%`,
                      }}
                    />
                  </span>
                  <span className={index === 0 ? 'text-primary' : ''}>
                    {formatDecimal(row.value)}
                  </span>
                </div>
              ))}
            </div>
            {(lowerCount || minimumRatio) && (
              <div className="mt-auto rounded-lg bg-secondary px-3.5 py-3 text-body-small">
                {lowerCount?.metric_code === 'LOWER_BENCHMARK_COUNT' && (
                  <p className="text-label-small text-primary">
                    우수 지역 {lowerCount.total_benchmark_count}곳 중{' '}
                    {formatCount(lowerCount.value)}곳보다 낮음
                  </p>
                )}
                {minimumRatio?.metric_code === 'MIN_BENCHMARK_SUPPLY_RATIO' && (
                  <p className="mt-1 text-muted-foreground">
                    가장 낮은 비교값은 {minimumRatio.benchmark_region_name} 대비{' '}
                    {formatRatio(minimumRatio.value)}입니다.
                  </p>
                )}
              </div>
            )}
          </article>

          <article className="flex flex-col gap-3 rounded-xl border bg-card p-5">
            <div>
              <p className="text-body-strong">등록 장소 1곳당 목적지 검색량</p>
              <p className="text-body-small text-muted-foreground">
                {evidence.searches_per_place.metric_definition}
              </p>
            </div>
            <div className="flex flex-col gap-1.5 py-1">
              {searchRows.map((row, index) => (
                <div
                  key={`${row.content_type}-${row.rank}`}
                  className="grid grid-cols-[minmax(5rem,auto)_minmax(6rem,1fr)_auto] items-center gap-2.5 text-body-small"
                >
                  <span>{TOURISM_CONTENT_LABEL[row.content_type]}</span>
                  <span className="h-2.5 overflow-hidden rounded-full bg-border/50">
                    <span
                      className={
                        index === 0
                          ? 'block h-full rounded-full bg-primary'
                          : index === 1
                            ? 'block h-full rounded-full bg-primary/75'
                            : 'block h-full rounded-full bg-muted-foreground/65'
                      }
                      style={{
                        width: `${getNormalizedBarWidth(
                          row.searches_per_place,
                          searchValues
                        )}%`,
                      }}
                    />
                  </span>
                  <span>{formatCount(row.searches_per_place)}</span>
                </div>
              ))}
            </div>
            <p className="mt-auto text-body-small text-muted-foreground">
              ※ {searchPressureDefinition}
            </p>
          </article>
        </div>
      </div>
    </section>
  );
}

export default DiagnosticEvidenceSection;
