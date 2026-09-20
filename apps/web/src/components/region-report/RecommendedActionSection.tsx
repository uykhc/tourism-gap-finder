import type {
  BenchmarkCaseDto,
  RecommendedActionDto,
} from '../../types/regionReport';
import {
  formatTwoDigitOrder,
  sortRecommendedActions,
} from '../../utils/regionReport';

interface RecommendedActionSectionProps {
  actions: RecommendedActionDto[];
  cases: BenchmarkCaseDto[];
}

function RecommendedActionSection({
  actions,
  cases,
}: RecommendedActionSectionProps) {
  if (actions.length === 0) return null;
  const caseById = new Map(cases.map((item) => [item.case_id, item]));

  return (
    <section className="bg-secondary/55">
      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-3 px-4 py-6 sm:px-8 lg:px-12">
        <h2>AI가 제안하는 인사이트</h2>
        <p className="text-body-small text-muted-foreground">
          현재 분석 결과와 참고 사례를 바탕으로 지역 관광자원을 활용할 수 있는
          방향을 제안합니다.
        </p>
        <div className="grid grid-cols-1 gap-4 pt-1 lg:grid-cols-2">
          {sortRecommendedActions(actions)
            .slice(0, 2)
            .map((action) => {
              const relatedCases = action.case_ids.flatMap((caseId) => {
                const relatedCase = caseById.get(caseId);
                return relatedCase ? [relatedCase] : [];
              });
              return (
                <article
                  key={action.order}
                  className="flex flex-col gap-3 rounded-xl border bg-card p-5"
                >
                  <div className="flex items-center gap-3">
                    <span className="rounded-full bg-primary px-2.5 py-2 text-label-small text-primary-foreground">
                      {formatTwoDigitOrder(action.order)}
                    </span>
                    <p className="text-body-strong">{action.title}</p>
                  </div>
                  <p className="text-body-small text-muted-foreground">
                    {action.rationale}
                  </p>
                  {action.evidence_texts.length > 0 && (
                    <ul className="flex flex-col gap-1 rounded-lg bg-secondary px-3 py-2.5 text-label-small text-primary">
                      {action.evidence_texts.map((evidenceText) => (
                        <li key={evidenceText}>{evidenceText}</li>
                      ))}
                    </ul>
                  )}
                  {relatedCases.length > 0 && (
                    <p className="text-body-small text-muted-foreground">
                      참고 사례 ·{' '}
                      {relatedCases.map((item) => item.title).join(', ')}
                    </p>
                  )}
                </article>
              );
            })}
        </div>
      </div>
    </section>
  );
}

export default RecommendedActionSection;
