import { useMutation, useQueryClient } from '@tanstack/react-query';
import { logout } from '../api/auth/logout';
import { clearAccessToken } from '../api/auth/session';
import { currentUserQueryKey } from './useCurrentUserQuery';

export default function useLogoutMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: logout,
    onSettled: () => {
      // 서버 로그아웃이 실패해도 이 브라우저에서는 인증 정보를 남기지 않는다.
      clearAccessToken();
      queryClient.removeQueries({ queryKey: currentUserQueryKey });
    },
  });
}
