import { http, HttpResponse, delay } from 'msw';
import { apiBaseUrl } from '../../api/client';
import { regionReportsById } from '../db/regionReports';

export const regionReportHandlers = [
  http.get(`${apiBaseUrl}/regions/:regionId/report`, async ({ params }) => {
    await delay(350);
    const regionId = String(params.regionId);
    if (regionId === '51110') {
      return HttpResponse.json(
        { detail: 'Report generation failed' },
        { status: 500 }
      );
    }
    if (regionId === '51130') {
      return HttpResponse.json(
        { detail: 'Authentication required' },
        { status: 401 }
      );
    }
    const report = regionReportsById[regionId];
    if (!report) {
      return HttpResponse.json(
        { detail: `Unknown region_id: ${regionId}` },
        { status: 404 }
      );
    }
    return HttpResponse.json(report);
  }),
];
