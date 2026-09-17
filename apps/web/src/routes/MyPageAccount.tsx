import { zodResolver } from '@hookform/resolvers/zod';
import { useState } from 'react';
import { useForm } from 'react-hook-form';
import { Navigate, useNavigate } from 'react-router';
import MyPageLayout from '../components/mypage/MyPageLayout';
import {
  type PasswordValues,
  passwordDefaultValues,
  passwordSchema,
} from '../components/mypage/passwordSchema';
import { Button } from '../components/ui/button';
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '../components/ui/dialog';
import { Input } from '../components/ui/input';
import { Label } from '../components/ui/label';
import useAccessToken from '../hooks/useAccessToken';
import useChangePasswordMutation from '../hooks/useChangePasswordMutation';
import useCurrentUserQuery from '../hooks/useCurrentUserQuery';
import useDeleteAccountMutation from '../hooks/useDeleteAccountMutation';
import { ApiError } from '../types/api';

function MyPageAccount() {
  const accessToken = useAccessToken();
  const navigate = useNavigate();
  const currentUserQuery = useCurrentUserQuery();
  const changePasswordMutation = useChangePasswordMutation();
  const deleteAccountMutation = useDeleteAccountMutation();
  const [passwordFeedback, setPasswordFeedback] = useState<{
    message: string;
    isError: boolean;
  } | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);
  const {
    register,
    handleSubmit,
    setError,
    reset,
    formState: { errors },
  } = useForm<PasswordValues>({
    resolver: zodResolver(passwordSchema),
    defaultValues: passwordDefaultValues,
    mode: 'onTouched',
  });

  if (accessToken === null) {
    return (
      <Navigate to="/login" replace state={{ returnTo: '/mypage/account' }} />
    );
  }

  const onSubmitPassword = handleSubmit(async (values) => {
    setPasswordFeedback(null);
    try {
      await changePasswordMutation.mutateAsync(values);
      reset(passwordDefaultValues);
      setPasswordFeedback({
        message: '비밀번호를 변경했어요.',
        isError: false,
      });
    } catch (error) {
      if (error instanceof ApiError && error.fields.length > 0) {
        for (const issue of error.fields) {
          if (
            issue.field === 'new_password' ||
            issue.field === 'new_password_confirm'
          ) {
            setError(issue.field, { type: 'server', message: issue.message });
          }
        }
        return;
      }
      setPasswordFeedback({
        message:
          error instanceof ApiError
            ? error.message
            : '비밀번호를 변경하지 못했어요. 다시 시도해 주세요.',
        isError: true,
      });
    } finally {
      changePasswordMutation.reset();
    }
  });

  const handleDeleteAccount = () => {
    setDeleteError(null);
    deleteAccountMutation.mutate(undefined, {
      onSuccess: () => {
        setDeleteDialogOpen(false);
        navigate('/', { replace: true });
      },
      onError: (error) => {
        setDeleteError(
          error instanceof ApiError
            ? error.message
            : '회원 탈퇴를 처리하지 못했어요. 다시 시도해 주세요.'
        );
      },
    });
  };

  return (
    <MyPageLayout>
      <h1>회원 정보</h1>
      <p className="text-body-small text-muted-foreground">
        로그인에 사용하는 계정 정보를 확인하고 변경할 수 있습니다.
      </p>

      <div className="flex w-full flex-col gap-3.5 rounded-xl border bg-card p-5">
        <h2 className="text-subheading">계정 정보</h2>
        <div className="flex flex-col gap-1.5">
          <div className="flex items-baseline gap-1.5">
            <Label htmlFor="account-email">이메일</Label>
            <span className="text-body-small text-muted-foreground">
              변경 불가
            </span>
          </div>
          <Input
            id="account-email"
            type="email"
            disabled
            value={currentUserQuery.data?.email ?? ''}
            placeholder={
              currentUserQuery.isPending ? '불러오는 중…' : undefined
            }
          />
        </div>
        <form
          noValidate
          aria-busy={changePasswordMutation.isPending}
          onSubmit={onSubmitPassword}
          className="flex flex-col gap-3.5"
        >
          {passwordFeedback && (
            <p
              role={passwordFeedback.isError ? 'alert' : 'status'}
              className={
                passwordFeedback.isError
                  ? 'text-body-small text-destructive'
                  : 'text-body-small text-primary'
              }
            >
              {passwordFeedback.message}
            </p>
          )}
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="account-new-password">새 비밀번호</Label>
            <Input
              id="account-new-password"
              type="password"
              placeholder="영문·숫자 포함 8자 이상"
              autoComplete="new-password"
              aria-invalid={Boolean(errors.new_password)}
              aria-describedby={
                errors.new_password ? 'account-new-password-error' : undefined
              }
              {...register('new_password')}
            />
            {errors.new_password && (
              <p
                id="account-new-password-error"
                role="alert"
                className="text-body-small text-destructive"
              >
                {errors.new_password.message}
              </p>
            )}
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="account-new-password-confirm">
              새 비밀번호 확인
            </Label>
            <Input
              id="account-new-password-confirm"
              type="password"
              placeholder="비밀번호를 한 번 더 입력해 주세요"
              autoComplete="new-password"
              aria-invalid={Boolean(errors.new_password_confirm)}
              aria-describedby={
                errors.new_password_confirm
                  ? 'account-new-password-confirm-error'
                  : undefined
              }
              {...register('new_password_confirm')}
            />
            {errors.new_password_confirm && (
              <p
                id="account-new-password-confirm-error"
                role="alert"
                className="text-body-small text-destructive"
              >
                {errors.new_password_confirm.message}
              </p>
            )}
          </div>
          <div className="flex justify-end">
            <Button
              type="submit"
              disabled={changePasswordMutation.isPending}
              className="w-full sm:w-37.5"
            >
              {changePasswordMutation.isPending ? '저장 중…' : '변경 내용 저장'}
            </Button>
          </div>
        </form>
      </div>

      <div className="flex w-full flex-col gap-2 rounded-xl border bg-card p-5">
        <h2 className="text-subheading">회원 탈퇴</h2>
        <p className="text-body-small text-muted-foreground">
          탈퇴하면 계정 정보와 관심 지역이 삭제되며 복구할 수 없습니다.
        </p>
        <Button
          type="button"
          variant="outline"
          className="w-fit border-destructive bg-destructive/5 text-destructive hover:bg-destructive/10"
          onClick={() => {
            setDeleteError(null);
            setDeleteDialogOpen(true);
          }}
        >
          회원 탈퇴
        </Button>
      </div>

      <Dialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <DialogContent className="max-w-md">
          <div className="flex flex-col gap-2">
            <DialogTitle>정말 탈퇴하시겠어요?</DialogTitle>
            <DialogDescription>
              탈퇴하면 계정 정보와 관심 지역이 삭제되며 복구할 수 없습니다.
            </DialogDescription>
          </div>
          {deleteError && (
            <p role="alert" className="text-body-small text-destructive">
              {deleteError}
            </p>
          )}
          <div className="flex justify-end gap-2.5">
            <DialogClose asChild>
              <Button
                type="button"
                variant="outline"
                disabled={deleteAccountMutation.isPending}
              >
                취소
              </Button>
            </DialogClose>
            <Button
              type="button"
              variant="destructive"
              disabled={deleteAccountMutation.isPending}
              onClick={handleDeleteAccount}
            >
              {deleteAccountMutation.isPending ? '처리 중…' : '탈퇴하기'}
            </Button>
          </div>
        </DialogContent>
      </Dialog>
    </MyPageLayout>
  );
}

export default MyPageAccount;
