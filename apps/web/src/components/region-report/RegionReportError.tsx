import { Link } from 'react-router';
import { Button } from '../ui/button';

interface RegionReportErrorProps {
  status: number | undefined;
  message: string;
  onRetry: () => void;
  onOpenRegionChange: () => void;
}

function RegionReportError({
  status,
  message,
  onRetry,
  onOpenRegionChange,
}: RegionReportErrorProps) {
  const isNotFound = status === 404;
  const isUnauthorized = status === 401;

  return (
    <section className="mx-auto flex w-full max-w-[1200px] flex-1 items-center justify-center px-4 py-16 sm:px-8 lg:px-12">
      <div
        role="alert"
        className="flex w-full max-w-xl flex-col items-start gap-4 rounded-xl border bg-card p-6"
      >
        <h1>
          {isNotFound
            ? '지역 보고서를 찾지 못했어요'
            : isUnauthorized
              ? '로그인이 필요해요'
              : '보고서를 불러오지 못했어요'}
        </h1>
        <p className="text-muted-foreground">{message}</p>
        {isNotFound ? (
          <Button type="button" onClick={onOpenRegionChange}>
            다른 지역 선택
          </Button>
        ) : isUnauthorized ? (
          <Button asChild>
            <Link to="/login">로그인하기</Link>
          </Button>
        ) : (
          <Button type="button" onClick={onRetry}>
            다시 시도
          </Button>
        )}
      </div>
    </section>
  );
}

export default RegionReportError;
