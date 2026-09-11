import type { ReactNode } from 'react';
import { Button } from '../ui/button';

export interface RegionSelectorConnection {
  value: string | null;
  onChange: (regionCode: string | null) => void;
  onComplete: (regionCode: string) => void;
  disabled: boolean;
  error: string | undefined;
}

export interface InterestRegionStepProps extends RegionSelectorConnection {
  regionSelector?: (connection: RegionSelectorConnection) => ReactNode;
  onSkip: () => void;
}

export default function InterestRegionStep({
  regionSelector,
  onSkip,
  ...connection
}: InterestRegionStepProps) {
  return (
    <div className="flex flex-col items-center gap-5">
      <div className="flex w-full max-w-[883.2px] flex-col gap-2 rounded-xl border bg-card p-4">
        <h1 id="signup-title" tabIndex={-1} className="outline-none">
          관심 지역을 설정해 주세요 (선택)
        </h1>
        <p className="text-muted-foreground">
          자주 확인할 지역을 선택하면 해당 지역의 관광 빈칸 대시보드를 먼저
          보여드려요.
        </p>
      </div>
      <div className="w-full max-w-[883.2px] pt-[38.4px] pb-3">
        {/* 팀원 카드가 완성되면 이 삽입 지점에서 실제 props만 연결한다. */}
        {regionSelector ? (
          regionSelector(connection)
        ) : (
          <div className="min-h-[250.1px]" aria-hidden="true" />
        )}
        {connection.error && (
          <p className="mt-3 text-body-small text-destructive" role="alert">
            {connection.error}
          </p>
        )}
      </div>
      <Button
        type="button"
        variant="ghost"
        className="h-auto p-0"
        disabled={connection.disabled}
        onClick={onSkip}
      >
        {connection.disabled ? '가입 처리 중…' : '건너뛰기'}
      </Button>
    </div>
  );
}
