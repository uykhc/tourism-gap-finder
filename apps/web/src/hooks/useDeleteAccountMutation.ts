import { useMutation, useQueryClient } from '@tanstack/react-query';
import { clearAccessToken } from '../api/auth/session';
import { deleteAccount } from '../api/users/me';
import { currentUserQueryKey } from './useCurrentUserQuery';

export default function useDeleteAccountMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: deleteAccount,
    onSuccess: () => {
      clearAccessToken();
      queryClient.removeQueries({ queryKey: currentUserQueryKey });
    },
  });
}
