import { useMutation, useQueryClient } from '@tanstack/react-query';
import { updateInterestRegion } from '../api/users/me';
import { currentUserQueryKey } from './useCurrentUserQuery';

export default function useUpdateInterestRegionMutation() {
  const queryClient = useQueryClient();

  return useMutation({
    mutationFn: updateInterestRegion,
    onSuccess: (user) => {
      queryClient.setQueryData(currentUserQueryKey, user);
    },
  });
}
