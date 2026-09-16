import {
  CASE_TYPE_LABEL,
  TOURISM_CONTENT_LABEL,
} from '../../constants/regionReport';
import type { BenchmarkCaseDto, SourceDto } from '../../types/regionReport';
import { resolveSources } from '../../utils/regionReport';
import { Button } from '../ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '../ui/dialog';

interface BenchmarkCaseDetailDialogProps {
  selectedCase: BenchmarkCaseDto | null;
  sources: SourceDto[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function BenchmarkCaseDetailDialog({
  selectedCase,
  sources,
  open,
  onOpenChange,
}: BenchmarkCaseDetailDialogProps) {
  const relatedSources = selectedCase
    ? resolveSources(selectedCase.source_ids, sources)
    : [];

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        {selectedCase && (
          <>
            <div className="flex flex-col gap-2">
              <DialogTitle>{selectedCase.title}</DialogTitle>
              <DialogDescription>
                {selectedCase.benchmark_region_name} ·{' '}
                {CASE_TYPE_LABEL[selectedCase.case_type]} ·{' '}
                {TOURISM_CONTENT_LABEL[selectedCase.content_type]}
              </DialogDescription>
            </div>
            <dl className="grid gap-4 text-body-small sm:grid-cols-2">
              <div className="rounded-lg bg-muted p-3">
                <dt className="text-label-small text-muted-foreground">
                  운영 기간
                </dt>
                <dd className="mt-2">{selectedCase.period || '—'}</dd>
              </div>
              <div className="rounded-lg bg-muted p-3">
                <dt className="text-label-small text-muted-foreground">
                  운영 주체
                </dt>
                <dd className="mt-2">{selectedCase.operator || '—'}</dd>
              </div>
            </dl>
            <div className="flex flex-col gap-2">
              <p className="text-body-strong">사례 요약</p>
              <p className="text-muted-foreground">{selectedCase.summary}</p>
            </div>
            <div className="flex flex-col gap-2 rounded-lg bg-secondary p-4">
              <p className="text-body-strong text-primary">적용할 때 볼 원리</p>
              <p className="text-muted-foreground">
                {selectedCase.applicability}
              </p>
            </div>
            <div className="flex flex-col gap-2">
              <p className="text-body-strong">출처</p>
              {relatedSources.length > 0 ? (
                <ul className="flex flex-col gap-2 text-body-small">
                  {relatedSources.map((source) => (
                    <li key={source.source_id}>
                      <a
                        href={source.url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-primary underline underline-offset-4"
                      >
                        {source.title} · {source.publisher}
                      </a>
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-body-small text-muted-foreground">
                  연결된 출처가 없습니다.
                </p>
              )}
            </div>
            <div className="flex justify-end">
              <DialogClose asChild>
                <Button type="button" variant="outline">
                  닫기
                </Button>
              </DialogClose>
            </div>
          </>
        )}
      </DialogContent>
    </Dialog>
  );
}

export default BenchmarkCaseDetailDialog;
