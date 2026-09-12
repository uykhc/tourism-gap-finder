import { useQuery } from '@tanstack/react-query';
import { fetchRegions } from '../api/regions';

export default function useRegionsQuery(province: string | null) {
  return useQuery({
    queryKey: ['regions', province],
    queryFn: () => fetchRegions(province ?? ''),
    enabled: province !== null,
    staleTime: Number.POSITIVE_INFINITY,
  });
}
