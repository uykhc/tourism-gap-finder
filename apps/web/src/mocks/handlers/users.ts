import { http, HttpResponse, delay } from 'msw';
import { z } from 'zod';
import { apiBaseUrl } from '../../api/client';
import { regions } from '../db/regions';
import { findMockUserByAccessToken, saveMockUsers } from '../db/users';

const updateUserSchema = z.object({
  default_region: z
    .string()
    .regex(/^\d{5}$/)
    .nullable(),
});

const getAccessToken = (request: Request): string | null => {
  const authorization = request.headers.get('authorization');
  return authorization?.startsWith('Bearer ')
    ? authorization.slice('Bearer '.length)
    : null;
};

export const userHandlers = [
  http.patch(`${apiBaseUrl}/users/me`, async ({ request }) => {
    await delay(250);
    const accessToken = getAccessToken(request);
    const record = accessToken
      ? findMockUserByAccessToken(accessToken)
      : undefined;
    if (!record) {
      return HttpResponse.json(
        { detail: 'Invalid or expired token' },
        { status: 401 }
      );
    }

    let body: unknown;
    try {
      body = await request.json();
    } catch {
      return HttpResponse.json({ detail: 'Invalid JSON' }, { status: 422 });
    }
    const parsed = updateUserSchema.safeParse(body);
    if (!parsed.success) {
      return HttpResponse.json(
        {
          detail: parsed.error.issues.map((issue) => ({
            type: issue.code,
            loc: ['body', ...issue.path],
            msg: issue.message,
          })),
        },
        { status: 422 }
      );
    }

    const region =
      regions.find((item) => item.region_id === parsed.data.default_region) ??
      null;
    if (parsed.data.default_region !== null && !region) {
      return HttpResponse.json(
        { detail: `Unknown region_id: ${parsed.data.default_region}` },
        { status: 422 }
      );
    }

    record.user = { ...record.user, default_region: region };
    saveMockUsers();
    return HttpResponse.json(record.user);
  }),
];
