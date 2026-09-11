import { zodResolver } from '@hookform/resolvers/zod';
import { useEffect, useRef, useState } from 'react';
import { FormProvider, useForm, useWatch } from 'react-hook-form';
import AccountInfoStep from '../components/signup/AccountInfoStep';
import InterestRegionStep, {
  type InterestRegionStepProps,
} from '../components/signup/InterestRegionStep';
import SignUpCompleteStep from '../components/signup/SignUpCompleteStep';
import SignUpProgress, {
  type SignUpStep,
} from '../components/signup/SignUpProgress';
import {
  type SignUpValues,
  accountFields,
  signupDefaultValues,
  signupSchema,
} from '../components/signup/signupSchema';
import useSignUpMutation from '../hooks/useSignUpMutation';
import { ApiError } from '../types/api';
import type { UserResponse } from '../types/auth';
import { cn } from '../utils/cn';

interface SignUpProps {
  regionSelector?: InterestRegionStepProps['regionSelector'];
}

export default function SignUp({ regionSelector }: SignUpProps) {
  // 1. 입력은 페이지가 열려 있는 동안만 유지하고 재진입 시 초기화한다.
  const [step, setStep] = useState<SignUpStep>('account');
  const [user, setUser] = useState<UserResponse | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const busy = useRef(false);
  const mounted = useRef(true);
  const container = useRef<HTMLDivElement>(null);
  const focusField = useRef<(typeof accountFields)[number] | null>(null);
  const methods = useForm<SignUpValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: signupDefaultValues,
    shouldUnregister: false,
    mode: 'onTouched',
    reValidateMode: 'onChange',
  });
  const {
    setFocus,
    setError,
    clearErrors,
    setValue,
    handleSubmit,
    trigger,
    reset,
    control,
    formState: { errors },
  } = methods;
  const regionCode = useWatch({ control, name: 'default_region' });
  const mutation = useSignUpMutation();

  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);

  useEffect(() => {
    if (step === 'account' && focusField.current) {
      setFocus(focusField.current);
      focusField.current = null;
    } else {
      container.current?.querySelector<HTMLElement>('#signup-title')?.focus();
    }
  }, [step, setFocus]);

  const showError = (error: unknown) => {
    if (!(error instanceof ApiError)) {
      setError('root.server', {
        message: '회원가입을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.',
      });
      return;
    }
    let firstAccountField: (typeof accountFields)[number] | undefined;
    for (const issue of error.fields) {
      const field = accountFields.find((name) => name === issue.field);
      if (field) {
        setError(field, { type: 'server', message: issue.message });
        firstAccountField ??= field;
      } else if (issue.field === 'default_region') {
        setError('default_region', { type: 'server', message: issue.message });
      }
    }
    if (firstAccountField) {
      focusField.current = firstAccountField;
      setStep('account');
    } else if (error.fields.length === 0) {
      setError('root.server', { type: 'server', message: error.message });
    }
  };

  // 2. 카드 완료와 건너뛰기는 동일한 검증·제출 경로를 사용한다.
  const submitRegion = async (nextRegion: string | null) => {
    if (busy.current || step !== 'region') return;
    busy.current = true;
    setSubmitting(true);
    clearErrors();
    setValue('default_region', nextRegion);
    try {
      await handleSubmit(
        async (values) => {
          if (!mounted.current) return;
          const result = await mutation.mutateAsync({
            ...values,
            default_region: nextRegion,
          });
          if (!mounted.current) return;
          // 추후 자동 로그인은 이 성공 처리 지점에 연결한다.
          setUser(result);
          reset(signupDefaultValues);
          setStep('complete');
        },
        (invalid) => {
          if (!mounted.current) return;
          const field = accountFields.find((name) => invalid[name]);
          if (field) {
            focusField.current = field;
            setStep('account');
          }
        }
      )();
    } catch (error) {
      if (mounted.current) showError(error);
    } finally {
      mutation.reset();
      busy.current = false;
      if (mounted.current) setSubmitting(false);
    }
  };

  const advanceAccount = async () => {
    if (busy.current) return;
    busy.current = true;
    clearErrors('root');
    try {
      if (
        (await trigger([...accountFields], { shouldFocus: true })) &&
        mounted.current
      )
        setStep('region');
    } finally {
      busy.current = false;
    }
  };

  const changeRegion = (value: string | null) => {
    if (busy.current) return;
    setValue('default_region', value, { shouldDirty: true });
    clearErrors('default_region');
  };

  return (
    <div ref={container} className="flex flex-1 flex-col break-keep bg-muted">
      <div
        className={cn(
          'mx-auto flex w-full max-w-[1200px] flex-col px-4 py-5 sm:px-8 lg:px-14',
          step === 'complete' ? 'gap-4' : 'gap-5'
        )}
      >
        <SignUpProgress step={step} />
        <FormProvider {...methods}>
          <form
            noValidate
            aria-labelledby="signup-title"
            aria-busy={submitting}
            onSubmit={(event) => {
              event.preventDefault();
              if (step === 'account') void advanceAccount();
            }}
          >
            {errors.root?.server?.message && (
              <p
                role="alert"
                className="mx-auto mb-4 w-full max-w-[760px] text-body-small text-destructive"
              >
                {errors.root.server.message}
              </p>
            )}
            {step === 'account' && <AccountInfoStep />}
            {step === 'region' && (
              <InterestRegionStep
                regionSelector={regionSelector}
                value={regionCode}
                disabled={submitting}
                error={errors.default_region?.message}
                onChange={changeRegion}
                onComplete={(value) => {
                  if (busy.current) return;
                  if (typeof value !== 'string' || !/^\d{5}$/.test(value)) {
                    setError('default_region', {
                      message: '관심 지역을 다시 선택해 주세요.',
                    });
                    return;
                  }
                  void submitRegion(value);
                }}
                onSkip={() => {
                  void submitRegion(null);
                }}
              />
            )}
            {step === 'complete' && user && <SignUpCompleteStep user={user} />}
          </form>
        </FormProvider>
      </div>
    </div>
  );
}
