import { http, HttpResponse, delay } from 'msw';
import { z } from 'zod';
import { apiBaseUrl } from '../../api/client';
import { regions } from '../db/regions';
import { findMockUserByAccessToken, saveMockUsers, users } from '../db/users';

const updateUserSchema = z.object({
  default_region: z
    .string()
    .regex(/^\d{5}$/)
    .nullable(),
});

const changePasswordSchema = z
  .object({
    new_password: z
      .string()
      .min(8)
      .max(128)
      .regex(/[A-Za-z]/)
      .regex(/\d/),
    new_password_confirm: z.string().min(8).max(128),
  })
  .refine((value) => value.new_password === value.new_password_confirm, {
    message: 'new_password and new_password_confirm must match',
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
  http.patch(`${apiBaseUrl}/users/me/password`, async ({ request }) => {
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
    const parsed = changePasswordSchema.safeParse(body);
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

    record.password = parsed.data.new_password;
    saveMockUsers();
    return new HttpResponse(null, { status: 204 });
  }),
  http.delete(`${apiBaseUrl}/users/me`, async ({ request }) => {
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

    users.delete(record.user.email);
    saveMockUsers();
    return new HttpResponse(null, { status: 204 });
  }),
];
