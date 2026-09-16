import type { MethodologyDto, SourceDto } from '../../types/regionReport';
import { Button } from '../ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '../ui/dialog';

interface MethodologyDetailDialogProps {
  methodology: MethodologyDto;
  sources: SourceDto[];
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

function MethodologyDetailDialog({
  methodology,
  sources,
  open,
  onOpenChange,
}: MethodologyDetailDialogProps) {
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <div className="flex flex-col gap-2">
          <DialogTitle>출처와 분석 방법</DialogTitle>
          <DialogDescription>
            비교 지역 선정과 지표 해석 기준, 분석의 한계를 확인합니다.
          </DialogDescription>
        </div>
        <dl className="flex flex-col gap-4">
          <div>
            <dt className="text-body-strong">비교 지역 선정 기준</dt>
            <dd className="mt-1 text-muted-foreground">
              {methodology.benchmark_selection_rule}
            </dd>
            <dd className="mt-1 text-body-small text-muted-foreground">
              {methodology.benchmark_selection_note}
            </dd>
          </div>
          <div>
            <dt className="text-body-strong">공급 비교 기준</dt>
            <dd className="mt-1 text-muted-foreground">
              {methodology.supply_comparison_rule}
            </dd>
          </div>
          <div>
            <dt className="text-body-strong">검색 압력 정의</dt>
            <dd className="mt-1 text-muted-foreground">
              {methodology.search_pressure_definition}
            </dd>
          </div>
        </dl>
        {methodology.provisional_notice && (
          <p className="rounded-lg bg-warning-muted p-3 text-body-small text-warning-foreground">
            {methodology.provisional_notice}
          </p>
        )}
        <div className="flex flex-col gap-2">
          <p className="text-body-strong">분석의 한계</p>
          {methodology.limitations.length > 0 ? (
            <ul className="list-disc space-y-1 pl-5 text-body-small text-muted-foreground">
              {methodology.limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          ) : (
            <p className="text-body-small text-muted-foreground">
              별도로 제공된 한계 정보가 없습니다.
            </p>
          )}
        </div>
        <div className="flex flex-col gap-2">
          <p className="text-body-strong">출처</p>
          {sources.length > 0 ? (
            <ul className="space-y-2 text-body-small">
              {sources.map((source) => (
                <li key={source.source_id}>
                  <a
                    href={source.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-primary underline underline-offset-4"
                  >
                    {source.title}
                  </a>
                  <span className="text-muted-foreground">
                    {' '}
                    · {source.publisher} · {source.published_at}
                  </span>
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
      </DialogContent>
    </Dialog>
  );
}

export default MethodologyDetailDialog;
