import { useEffect, useRef } from 'react';
import { useFormContext, useWatch } from 'react-hook-form';
import { Button } from '../ui/button';
import { Input } from '../ui/input';
import { Label } from '../ui/label';
import type { SignUpValues } from './signupSchema';

const fields = [
  {
    name: 'email',
    label: '이메일',
    placeholder: 'example@email.com',
    type: 'email',
    autoComplete: 'email',
  },
  {
    name: 'password',
    label: '비밀번호',
    placeholder: '영문·숫자 포함 8자 이상',
    type: 'password',
    autoComplete: 'new-password',
  },
  {
    name: 'password_confirm',
    label: '비밀번호 확인',
    placeholder: '비밀번호를 한 번 더 입력해 주세요',
    type: 'password',
    autoComplete: 'new-password',
  },
] as const;

export default function AccountInfoStep() {
  const {
    register,
    control,
    trigger,
    formState: { errors, touchedFields },
  } = useFormContext<SignUpValues>();
  const password = useWatch({ control, name: 'password' });
  const confirmationTouched = touchedFields.password_confirm;
  const previousPassword = useRef(password);

  useEffect(() => {
    if (confirmationTouched && previousPassword.current !== password) {
      void trigger('password_confirm');
    }
    previousPassword.current = password;
  }, [password, confirmationTouched, trigger]);

  return (
    <div className="mx-auto flex w-full max-w-[760px] flex-col gap-2.5 rounded-xl border bg-card px-6 py-4">
      <h1 id="signup-title" tabIndex={-1} className="outline-none">
        계정 정보를 입력해 주세요
      </h1>
      <p className="text-muted-foreground">
        로그인에 사용할 기본 정보를 입력해 주세요.
      </p>
      {fields.map((field) => (
        <div key={field.name} className="flex flex-col gap-1.5">
          <Label htmlFor={`signup-${field.name}`}>{field.label}</Label>
          <Input
            id={`signup-${field.name}`}
            type={field.type}
            placeholder={field.placeholder}
            autoComplete={field.autoComplete}
            aria-invalid={Boolean(errors[field.name])}
            aria-describedby={
              errors[field.name] ? `signup-${field.name}-error` : undefined
            }
            {...register(field.name)}
          />
          {errors[field.name] && (
            <p
              id={`signup-${field.name}-error`}
              className="text-body-small text-destructive"
              role="alert"
            >
              {errors[field.name]?.message}
            </p>
          )}
        </div>
      ))}
      <Button type="submit" className="h-12 w-full">
        관심 지역 설정으로
      </Button>
      <p className="text-body-small text-muted-foreground">
        관심 지역은 다음 단계에서 선택하거나 건너뛸 수 있어요.
      </p>
    </div>
  );
}
