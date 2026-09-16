import {
  DETAIL_SIGNAL_LABEL,
  KEY_METRIC_TITLE,
  TOURISM_CONTENT_LABEL,
} from '../../constants/regionReport';
import type {
  DetailedDiagnosisDto,
  GapSignalLevel,
  QuantitativeEvidenceDto,
} from '../../types/regionReport';
import { cn } from '../../utils/cn';
import {
  formatCount,
  formatDecimal,
  formatRatio,
} from '../../utils/regionReport';

const getCardClassName = (signalLevel: GapSignalLevel) => {
  if (signalLevel === 'STRONG_GAP_CANDIDATE') {
    return 'border-primary bg-secondary';
  }
  if (signalLevel === 'NEEDS_REVIEW') {
    return 'border-warning bg-warning-muted';
  }
  return 'border-border bg-muted';
};

const getAccentClassName = (signalLevel: GapSignalLevel) =>
  signalLevel === 'NEEDS_REVIEW' ? 'text-warning-foreground' : 'text-primary';

const getEvidenceText = (evidence: QuantitativeEvidenceDto) => {
  switch (evidence.metric_code) {
    case 'MIN_BENCHMARK_SUPPLY_RATIO':
      return evidence.comparisons.length > 0
        ? evidence.comparisons
            .map(
              (comparison) =>
                `${comparison.region_name} 대비 ${formatRatio(
                  comparison.target_to_benchmark_ratio
                )}`
            )
            .join(' · ')
        : `최저 ${formatRatio(evidence.value)}`;
    case 'LOWER_BENCHMARK_COUNT':
      return `${formatCount(evidence.value)}곳보다 낮음`;
    case 'SEARCHES_PER_PLACE':
      return evidence.rank && evidence.total_count
        ? `${formatCount(evidence.value)}회 · ${evidence.total_count}개 유형 중 ${evidence.rank}위`
        : `${formatCount(evidence.value)}회`;
    case 'SUPPLY_PLACE_COUNT':
      return `${formatCount(evidence.value)}개`;
    case 'SUPPLY_DENSITY_PER_100_KM2':
      return `${formatDecimal(evidence.value)}개/100㎢`;
    case 'UNKNOWN':
      return formatDecimal(evidence.value);
  }
};

interface DetailedDiagnosisSectionProps {
  diagnoses: DetailedDiagnosisDto[];
}

function DetailedDiagnosisSection({
  diagnoses,
}: DetailedDiagnosisSectionProps) {
  if (diagnoses.length === 0) return null;

  return (
    <section className="bg-card">
      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-3 px-4 py-6 sm:px-8 lg:px-12">
        <h2>분야별 상세 진단</h2>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          {diagnoses.map((diagnosis) => (
            <article
              key={diagnosis.content_type}
              className={cn(
                'flex flex-col gap-3 rounded-xl border p-4.5',
                getCardClassName(diagnosis.signal_level)
              )}
            >
              <div>
                <p
                  className={cn(
                    'text-label-small',
                    getAccentClassName(diagnosis.signal_level)
                  )}
                >
                  {DETAIL_SIGNAL_LABEL[diagnosis.signal_level]}
                </p>
                <p className="mt-2 text-body-strong">
                  {TOURISM_CONTENT_LABEL[diagnosis.content_type]}
                </p>
              </div>
              <p className="text-body-small text-muted-foreground">
                {diagnosis.judgement}
              </p>
              {diagnosis.quantitative_evidence.length > 0 && (
                <ul className="flex flex-wrap gap-2" aria-label="정량 근거">
                  {diagnosis.quantitative_evidence.map((evidence, index) => (
                    <li
                      key={`${evidence.metric_code}-${index}`}
                      className={cn(
                        'rounded-lg bg-card px-2.5 py-2 text-label-small',
                        getAccentClassName(diagnosis.signal_level)
                      )}
                    >
                      {KEY_METRIC_TITLE[evidence.metric_code]} ·{' '}
                      {getEvidenceText(evidence)}
                    </li>
                  ))}
                </ul>
              )}
              <p className="text-body-small text-muted-foreground">
                <strong>적용 관점</strong> · {diagnosis.applicability_insight}
              </p>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export default DetailedDiagnosisSection;
