import { useState } from 'react';
import {
  CASE_TYPE_LABEL,
  TOURISM_CONTENT_LABEL,
} from '../../constants/regionReport';
import type {
  BenchmarkCaseDto,
  MethodologyDto,
  SourceDto,
} from '../../types/regionReport';
import { Button } from '../ui/button';
import BenchmarkCaseDetailDialog from './BenchmarkCaseDetailDialog';
import MethodologyDetailDialog from './MethodologyDetailDialog';

interface CasesAndMethodologySectionProps {
  cases: BenchmarkCaseDto[];
  methodology: MethodologyDto;
  sources: SourceDto[];
}

function CasesAndMethodologySection({
  cases,
  methodology,
  sources,
}: CasesAndMethodologySectionProps) {
  const [selectedCase, setSelectedCase] = useState<BenchmarkCaseDto | null>(
    null
  );
  const [methodologyOpen, setMethodologyOpen] = useState(false);

  return (
    <section className="bg-card">
      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-3 px-4 py-6 sm:px-8 lg:px-12">
        <h2>참고 사례와 분석 기준</h2>
        <p className="text-body-small text-muted-foreground">
          지역을 모방하기보다 기존 자원에 경험을 더한 운영 원리를 참고합니다.
        </p>
        <div className="grid grid-cols-1 gap-4 pt-1 lg:grid-cols-[minmax(0,2fr)_minmax(18rem,1fr)]">
          <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
            {cases.length > 0 ? (
              cases.map((item) => (
                <Button
                  key={item.case_id}
                  type="button"
                  variant="outline"
                  onClick={() => setSelectedCase(item)}
                  className="h-auto min-h-28 items-start justify-start whitespace-normal rounded-[10px] bg-muted/70 p-4 text-left"
                >
                  <span className="flex min-w-0 flex-col items-start gap-2">
                    <span className="text-label-small text-primary">
                      {item.benchmark_region_name} ·{' '}
                      {CASE_TYPE_LABEL[item.case_type]}
                    </span>
                    <span className="text-body-strong">{item.title}</span>
                    <span className="text-body-small text-muted-foreground">
                      {TOURISM_CONTENT_LABEL[item.content_type]} · 사례 원리
                      확인하기 →
                    </span>
                  </span>
                </Button>
              ))
            ) : (
              <div className="rounded-xl border bg-muted/50 p-5 text-body-small text-muted-foreground sm:col-span-2">
                제공된 참고 사례가 없습니다.
              </div>
            )}
          </div>

          <article className="flex flex-col gap-3 rounded-xl bg-secondary p-4.5">
            <p className="text-body-strong">분석 기준과 한계</p>
            <ul className="list-disc space-y-2 pl-5 text-body-small text-muted-foreground">
              <li>{methodology.benchmark_selection_rule}</li>
              <li>{methodology.supply_comparison_rule}</li>
              <li>{methodology.search_pressure_definition}</li>
            </ul>
            {methodology.provisional_notice && (
              <p className="rounded-lg bg-card px-3 py-2 text-label-small text-warning-foreground">
                {methodology.provisional_notice}
              </p>
            )}
            <Button
              type="button"
              variant="link"
              onClick={() => setMethodologyOpen(true)}
              className="mt-auto h-auto justify-start p-0 text-label-small"
            >
              출처와 분석 방법 자세히 보기 →
            </Button>
          </article>
        </div>
      </div>

      <BenchmarkCaseDetailDialog
        selectedCase={selectedCase}
        sources={sources}
        open={selectedCase !== null}
        onOpenChange={(open) => {
          if (!open) setSelectedCase(null);
        }}
      />
      <MethodologyDetailDialog
        methodology={methodology}
        sources={sources}
        open={methodologyOpen}
        onOpenChange={setMethodologyOpen}
      />
    </section>
  );
}

export default CasesAndMethodologySection;
