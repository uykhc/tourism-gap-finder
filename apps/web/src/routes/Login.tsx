import { zodResolver } from '@hookform/resolvers/zod';
import { useForm } from 'react-hook-form';
import { Link, useNavigate } from 'react-router';
import {
  type LoginValues,
  loginDefaultValues,
  loginSchema,
} from '../components/login/loginSchema';
import { Button } from '../components/ui/button';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import useLoginMutation from '../hooks/useLoginMutation';
import { ApiError } from '../types/api';

function Login() {
  const navigate = useNavigate();
  const mutation = useLoginMutation();
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: loginDefaultValues,
    mode: 'onTouched',
  });

  const onSubmit = handleSubmit(async (values) => {
    try {
      await mutation.mutateAsync(values);
      navigate('/');
    } catch (error) {
      setError('root.server', {
        message:
          error instanceof ApiError
            ? error.message
            : '로그인을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.',
      });
    } finally {
      mutation.reset();
    }
  });

  return (
    <div className="flex flex-1 items-center justify-center bg-muted p-6">
      <div className="flex w-full max-w-120 flex-col gap-3 rounded-xl border bg-card p-8">
        <h1>다시 만나서 반가워요</h1>
        <p className="text-body-small text-muted-foreground">
          로그인하면 관심 지역의 분석 결과를 바로 확인할 수 있어요.
        </p>
        <form
          noValidate
          aria-busy={mutation.isPending}
          onSubmit={onSubmit}
          className="flex w-full flex-col gap-3"
        >
          {errors.root?.server?.message && (
            <p role="alert" className="text-body-small text-destructive">
              {errors.root.server.message}
            </p>
          )}
          <div className="flex flex-col gap-2">
            <Label htmlFor="login-email">이메일</Label>
            <Input
              id="login-email"
              type="email"
              placeholder="example@email.com"
              autoComplete="email"
              className="h-13 text-label"
              aria-invalid={Boolean(errors.email)}
              aria-describedby={errors.email ? 'login-email-error' : undefined}
              {...register('email')}
            />
            {errors.email && (
              <p
                id="login-email-error"
                role="alert"
                className="text-body-small text-destructive"
              >
                {errors.email.message}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-2">
            <Label htmlFor="login-password">비밀번호</Label>
            <Input
              id="login-password"
              type="password"
              placeholder="비밀번호를 입력해 주세요"
              autoComplete="current-password"
              className="h-13 text-label"
              aria-invalid={Boolean(errors.password)}
              aria-describedby={
                errors.password ? 'login-password-error' : undefined
              }
              {...register('password')}
            />
            {errors.password && (
              <p
                id="login-password-error"
                role="alert"
                className="text-body-small text-destructive"
              >
                {errors.password.message}
              </p>
            )}
          </div>
          <Button
            type="submit"
            disabled={mutation.isPending}
            className="h-13 w-full"
          >
            로그인
          </Button>
        </form>
        <div className="flex w-full items-center gap-3">
          <div className="h-px flex-1 bg-border" />
          <p className="text-body-small text-muted-foreground">또는</p>
          <div className="h-px flex-1 bg-border" />
        </div>
        <Button asChild variant="outline" className="h-13 w-full">
          <Link to="/signup">회원가입하고 관심 지역 설정하기</Link>
        </Button>
        <p className="text-body-small text-muted-foreground">
          비회원도 지역 분석은 이용할 수 있습니다.
        </p>
      </div>
    </div>
  );
}

export default Login;
