import { useQuery } from '@tanstack/react-query';
import { fetchRegionReport } from '../api/regions/tourismReport';

export default function useRegionReportQuery(regionId: string | null) {
  return useQuery({
    queryKey: ['region-report', regionId],
    queryFn: () => fetchRegionReport(regionId ?? ''),
    enabled: regionId !== null,
    retry: false,
    staleTime: 5 * 60 * 1000,
  });
}
