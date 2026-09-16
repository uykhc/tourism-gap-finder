import { queryOptions, useQuery } from '@tanstack/react-query';
import { fetchCurrentUser } from '../api/auth/me';
import useAccessToken from './useAccessToken';

export const currentUserQueryKey = ['auth', 'me'] as const;

export const currentUserQueryOptions = queryOptions({
  queryKey: currentUserQueryKey,
  queryFn: fetchCurrentUser,
  staleTime: 5 * 60 * 1000,
  retry: false,
});

export default function useCurrentUserQuery() {
  const accessToken = useAccessToken();
  return useQuery({
    ...currentUserQueryOptions,
    enabled: accessToken !== null,
  });
}
