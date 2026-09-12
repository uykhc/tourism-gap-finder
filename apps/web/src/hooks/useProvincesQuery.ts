import { useQuery } from '@tanstack/react-query';
import { fetchProvinces } from '../api/regions';

export default function useProvincesQuery() {
  return useQuery({
    queryKey: ['provinces'],
    queryFn: fetchProvinces,
    staleTime: Number.POSITIVE_INFINITY,
  });
}
