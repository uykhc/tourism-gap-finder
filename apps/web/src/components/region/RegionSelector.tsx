import { useState } from 'react';
import useProvincesQuery from '../../hooks/useProvincesQuery';
import useRegionsQuery from '../../hooks/useRegionsQuery';
import { cn } from '../../utils/cn';
import { Button } from '../ui/button';

interface RegionSelectorProps {
  value: string | null;
  onChange: (regionCode: string | null) => void;
  onComplete: (regionCode: string) => void;
  disabled?: boolean;
  completeLabel?: string;
}

interface StepChipProps {
  state: 'active' | 'done' | 'next';
  children: string;
}

function StepChip({ state, children }: StepChipProps) {
  return (
    <li
      aria-current={state === 'active' ? 'step' : undefined}
      className={cn(
        'flex h-7 items-center gap-1.5 rounded-full px-3 text-label-small',
        state === 'next'
          ? 'bg-muted text-muted-foreground'
          : 'bg-secondary text-secondary-foreground'
      )}
    >
      {children}
    </li>
  );
}

interface PillProps {
  label: string;
  selected: boolean;
  disabled: boolean;
  onClick: () => void;
}

function Pill({ label, selected, disabled, onClick }: PillProps) {
  return (
    <button
      type="button"
      aria-pressed={selected}
      disabled={disabled}
      onClick={onClick}
      className={cn(
        'flex h-8 shrink-0 items-center gap-1.5 rounded-full border px-3.5 text-label-small outline-none transition-colors disabled:pointer-events-none disabled:opacity-50 focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40',
        selected
          ? 'border-primary bg-primary text-primary-foreground'
          : 'border-border bg-card text-foreground hover:bg-muted'
      )}
    >
      {selected && <span aria-hidden="true">✓</span>}
      {label}
    </button>
  );
}

interface ListStatusProps {
  pending: boolean;
  errorMessage: string | undefined;
  emptyMessage: string;
  empty: boolean;
  onRetry: () => void;
}

function ListStatus({
  pending,
  errorMessage,
  emptyMessage,
  empty,
  onRetry,
}: ListStatusProps) {
  if (pending) {
    return (
      <p className="text-body-small text-muted-foreground">
        지역 목록을 불러오는 중…
      </p>
    );
  }
  if (errorMessage) {
    return (
      <div className="flex flex-wrap items-center gap-2.5">
        <p className="text-body-small text-destructive" role="alert">
          {errorMessage}
        </p>
        <Button type="button" variant="outline" size="sm" onClick={onRetry}>
          다시 시도
        </Button>
      </div>
    );
  }
  if (empty) {
    return (
      <p className="text-body-small text-muted-foreground">{emptyMessage}</p>
    );
  }
  return null;
}

export default function RegionSelector({
  value,
  onChange,
  onComplete,
  disabled = false,
  completeLabel = '관심 지역 설정하고 가입 완료',
}: RegionSelectorProps) {
  const [province, setProvince] = useState<string | null>(null);
  const [step, setStep] = useState<'province' | 'district'>('province');
  const provincesQuery = useProvincesQuery();
  const regionsQuery = useRegionsQuery(step === 'district' ? province : null);

  const districts = regionsQuery.data ?? [];
  const selectedDistrict =
    districts.find((district) => district.region_id === value) ?? null;

  const selectProvince = (name: string) => {
    if (name !== province && value !== null) onChange(null);
    setProvince(name);
  };

  const summaryText =
    step === 'province'
      ? province
      : selectedDistrict &&
        `${selectedDistrict.province_name} ${selectedDistrict.region_name}`;

  return (
    <div className="flex w-full flex-col gap-3.5 rounded-xl border bg-card p-6">
      {step === 'district' && province && (
        <div className="flex h-10 items-center justify-between gap-2.5 rounded-lg border bg-secondary px-3.5 text-label-small text-secondary-foreground">
          <p className="truncate">시·도 · {province}</p>
          <button
            type="button"
            disabled={disabled}
            onClick={() => setStep('province')}
            className="shrink-0 rounded-sm outline-none hover:underline disabled:pointer-events-none disabled:opacity-50 focus-visible:ring-2 focus-visible:ring-ring/40"
          >
            변경
          </button>
        </div>
      )}
      <ol className="flex flex-wrap gap-2">
        <StepChip state={step === 'province' ? 'active' : 'done'}>
          {step === 'province' ? '1 시·도 선택' : '✓ 시·도 선택'}
        </StepChip>
        <StepChip state={step === 'province' ? 'next' : 'active'}>
          2 시·군·구 선택
        </StepChip>
      </ol>
      {step === 'province' ? (
        <div className="flex flex-wrap gap-2">
          <ListStatus
            pending={provincesQuery.isPending}
            errorMessage={
              provincesQuery.isError
                ? '시·도 목록을 불러오지 못했어요.'
                : undefined
            }
            empty={provincesQuery.data?.length === 0}
            emptyMessage="선택할 수 있는 시·도가 없어요."
            onRetry={() => void provincesQuery.refetch()}
          />
          {provincesQuery.data?.map((item) => (
            <Pill
              key={item.province_name}
              label={item.province_name}
              selected={item.province_name === province}
              disabled={disabled}
              onClick={() => selectProvince(item.province_name)}
            />
          ))}
        </div>
      ) : (
        <div className="flex flex-wrap gap-2">
          <ListStatus
            pending={regionsQuery.isPending}
            errorMessage={
              regionsQuery.isError
                ? '시·군·구 목록을 불러오지 못했어요.'
                : undefined
            }
            empty={districts.length === 0 && regionsQuery.isSuccess}
            emptyMessage="선택할 수 있는 시·군·구가 없어요."
            onRetry={() => void regionsQuery.refetch()}
          />
          {districts.map((district) => (
            <Pill
              key={district.region_id}
              label={district.region_name}
              selected={district.region_id === value}
              disabled={disabled}
              onClick={() => onChange(district.region_id)}
            />
          ))}
        </div>
      )}
      <div className="flex w-full flex-col gap-2.5 sm:flex-row">
        <div className="flex min-w-0 flex-1 flex-col justify-center gap-1 rounded-lg border bg-muted px-3.5 py-2">
          <p className="text-label-small text-muted-foreground">선택 지역</p>
          {summaryText ? (
            <p className="truncate text-label-small text-foreground">
              {summaryText}
            </p>
          ) : (
            <p className="truncate text-label-small text-muted-foreground">
              {step === 'province'
                ? '시·도를 선택해 주세요'
                : '시·군·구를 선택해 주세요'}
            </p>
          )}
        </div>
        {step === 'province' ? (
          <Button
            type="button"
            disabled={disabled || province === null}
            onClick={() => setStep('district')}
            className="h-12 text-label-small sm:w-60"
          >
            다음으로
          </Button>
        ) : (
          <Button
            type="button"
            disabled={disabled || selectedDistrict === null}
            onClick={() => {
              if (selectedDistrict) onComplete(selectedDistrict.region_id);
            }}
            className="h-12 text-label-small sm:w-60"
          >
            {completeLabel}
          </Button>
        )}
      </div>
    </div>
  );
}
