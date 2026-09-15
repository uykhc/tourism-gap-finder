import { Bookmark } from 'lucide-react';
import { TOURISM_CONTENT_LABEL } from '../../constants/regionReport';
import type {
  AnalysisPeriodDto,
  RegionDto,
  ReportStatus,
  ReportSummaryDto,
} from '../../types/regionReport';
import { formatYearMonthRange } from '../../utils/regionReport';
import { Button } from '../ui/button';

interface InterestAction {
  isInterested: boolean;
  isPending: boolean;
  onToggleInterest: () => void;
  feedback: {
    message: string;
    isError: boolean;
  } | null;
}

interface ReportHeroProps {
  target: RegionDto;
  analysisPeriod: AnalysisPeriodDto;
  summary: ReportSummaryDto;
  reportStatus: ReportStatus;
  interestAction: InterestAction;
  onOpenRegionChange: () => void;
}

function ReportHero({
  target,
  analysisPeriod,
  summary,
  reportStatus,
  interestAction,
  onOpenRegionChange,
}: ReportHeroProps) {
  const primaryLabel = summary.primary_gap_type
    ? TOURISM_CONTENT_LABEL[summary.primary_gap_type]
    : null;

  return (
    <section className="bg-secondary">
      <div className="mx-auto grid w-full max-w-[1200px] gap-6 px-4 py-8 sm:px-8 lg:grid-cols-[1fr_280px] lg:items-center lg:px-12">
        <div className="flex min-w-0 flex-col gap-3">
          <p className="text-body-small text-primary">
            {target.province_name} · {target.region_name} 관광 빈칸 리포트
          </p>
          <h1 className="max-w-3xl">{summary.one_line_review.text}</h1>
          <div className="flex flex-wrap gap-2 pt-1">
            {summary.diagnosis_status === 'GAP_FOUND' && primaryLabel && (
              <span className="rounded-full bg-primary px-3 py-2 text-label-small text-primary-foreground">
                우선 검증 · {primaryLabel}
              </span>
            )}
            {reportStatus === 'PROVISIONAL' && (
              <span className="rounded-full border bg-card px-3 py-2 text-label-small text-muted-foreground">
                잠정 분석
              </span>
            )}
            {summary.diagnosis_status === 'NO_CLEAR_GAP' && (
              <span className="rounded-full border bg-card px-3 py-2 text-label-small text-muted-foreground">
                뚜렷한 대표 빈칸 없음
              </span>
            )}
            {summary.diagnosis_status === 'INSUFFICIENT_DATA' && (
              <span className="rounded-full border border-warning bg-warning-muted px-3 py-2 text-label-small text-warning-foreground">
                데이터 부족
              </span>
            )}
          </div>
        </div>

        <div className="flex flex-col gap-2.5 rounded-xl border bg-card p-5">
          <p className="text-body-small text-muted-foreground">분석 대상</p>
          <p className="text-body-strong">
            {target.province_name} {target.region_name}
          </p>
          <p className="text-body-small text-muted-foreground">
            분석 기간{' '}
            {formatYearMonthRange(
              analysisPeriod.start_ym,
              analysisPeriod.end_ym
            )}
          </p>
          <div className="flex flex-wrap gap-2 pt-1">
            <Button
              type="button"
              size="sm"
              disabled={interestAction.isPending}
              aria-busy={interestAction.isPending}
              aria-pressed={interestAction.isInterested}
              aria-label={
                interestAction.isInterested
                  ? `${target.region_name}를 관심 지역에서 해제`
                  : `${target.region_name}를 관심 지역으로 설정`
              }
              title={
                interestAction.isInterested ? '관심 지역에서 해제' : undefined
              }
              onClick={interestAction.onToggleInterest}
              className="gap-1.5"
            >
              <Bookmark
                aria-hidden="true"
                className="size-3.5 shrink-0"
                fill={interestAction.isInterested ? 'currentColor' : 'none'}
                strokeWidth={1.75}
              />
              {interestAction.isInterested ? '관심 지역' : '관심 지역으로 설정'}
            </Button>
            <Button
              type="button"
              size="sm"
              variant="outline"
              onClick={onOpenRegionChange}
              className="text-primary"
            >
              지역 변경
            </Button>
          </div>
          {interestAction.feedback && (
            <p
              role={interestAction.feedback.isError ? 'alert' : 'status'}
              className={
                interestAction.feedback.isError
                  ? 'text-body-small text-destructive'
                  : 'text-body-small text-primary'
              }
            >
              {interestAction.feedback.message}
            </p>
          )}
        </div>
      </div>
    </section>
  );
}

export default ReportHero;
