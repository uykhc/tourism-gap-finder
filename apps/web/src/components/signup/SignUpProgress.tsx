import { cn } from '../../utils/cn';

export type SignUpStep = 'account' | 'region' | 'complete';

interface ProgressStep {
  id: SignUpStep;
  label: string;
}

const steps: ProgressStep[] = [
  { id: 'account', label: '계정 정보' },
  { id: 'region', label: '관심 지역' },
  { id: 'complete', label: '가입 완료' },
];

export default function SignUpProgress({ step }: { step: SignUpStep }) {
  return (
    <ol
      aria-label="회원가입 진행 단계"
      className="mx-auto flex w-full max-w-[760px] items-center gap-3"
    >
      {steps.map((item, index) => (
        <li
          key={item.id}
          aria-current={step === item.id ? 'step' : undefined}
          className="flex min-w-0 flex-1 flex-col items-center gap-2 sm:flex-row"
        >
          <span
            aria-hidden="true"
            className={cn(
              'flex size-8 shrink-0 items-center justify-center rounded-full text-label-small',
              step === item.id
                ? 'bg-primary text-primary-foreground'
                : 'bg-secondary text-secondary-foreground'
            )}
          >
            {index + 1}
          </span>
          <span
            className={cn(
              'whitespace-nowrap text-label-small',
              step === item.id ? 'text-foreground' : 'text-muted-foreground'
            )}
          >
            {item.label}
          </span>
        </li>
      ))}
    </ol>
  );
}
