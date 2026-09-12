import { http, HttpResponse, delay } from 'msw';
import { apiBaseUrl } from '../../api/client';
import { provinces, regions } from '../db/regions';

export const regionHandlers = [
  http.get(`${apiBaseUrl}/provinces`, async () => {
    await delay(200);
    return HttpResponse.json({ items: provinces, total: provinces.length });
  }),
  http.get(`${apiBaseUrl}/regions`, async ({ request }) => {
    await delay(250);
    const url = new URL(request.url);
    const q = url.searchParams.get('q');
    const province = url.searchParams.get('province');
    let items = regions;
    if (province) {
      items = items.filter((item) => item.province_name === province);
    }
    if (q) {
      items = items.filter((item) => item.region_name.includes(q));
    }
    return HttpResponse.json({ items, total: items.length });
  }),
];
