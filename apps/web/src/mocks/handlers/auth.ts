import { http, HttpResponse, delay } from 'msw';
import { z } from 'zod';
import { apiBaseUrl } from '../../api/client';
import type { UserResponse } from '../../types/auth';
import { regions } from '../db/regions';
import {
  createMockAccessToken,
  findMockUserByAccessToken,
  saveMockUsers,
  users,
} from '../db/users';

// 백엔드의 동의 필드 삭제 후 계약을 모킹한다. 현재 서버와의 차이는 README에 기록한다.
const requestSchema = z
  .object({
    email: z.string().email(),
    password: z
      .string()
      .min(8)
      .max(128)
      .regex(/[A-Za-z]/)
      .regex(/\d/),
    password_confirm: z.string().min(8).max(128),
    default_region: z
      .string()
      .regex(/^\d{5}$/)
      .nullable()
      .default(null),
  })
  .refine((value) => value.password === value.password_confirm, {
    message: 'password and password_confirm must match',
  });

const loginRequestSchema = z.object({
  email: z.string().email(),
  password: z.string().min(1),
});

const getAccessToken = (request: Request): string | null => {
  const authorization = request.headers.get('authorization');
  return authorization?.startsWith('Bearer ')
    ? authorization.slice('Bearer '.length)
    : null;
};

export const authHandlers = [
  http.post(`${apiBaseUrl}/auth/signup`, async ({ request }) => {
    await delay(350);
    let body: unknown;
    try {
      body = await request.json();
    } catch {
      return HttpResponse.json({ detail: 'Invalid JSON' }, { status: 422 });
    }
    const parsed = requestSchema.safeParse(body);
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
    const payload = parsed.data;
    const email = payload.email.toLowerCase();
    if (users.has(email)) {
      return HttpResponse.json(
        { detail: 'Email is already registered' },
        { status: 409 }
      );
    }
    const region =
      regions.find((item) => item.region_id === payload.default_region) ?? null;
    if (payload.default_region !== null && !region) {
      return HttpResponse.json(
        { detail: `Unknown region_id: ${payload.default_region}` },
        { status: 422 }
      );
    }
    const user: UserResponse = {
      id: users.size + 1,
      email,
      default_region: region,
      created_at: new Date().toISOString(),
    };
    // 비밀번호는 실제 응답에 포함하지 않고 개발용 로그인 검증 레코드에만 둔다.
    users.set(email, { user, password: payload.password });
    saveMockUsers();
    return HttpResponse.json(user, { status: 201 });
  }),
  http.post(`${apiBaseUrl}/auth/login`, async ({ request }) => {
    await delay(250);
    let body: unknown;
    try {
      body = await request.json();
    } catch {
      return HttpResponse.json({ detail: 'Invalid JSON' }, { status: 422 });
    }
    const parsed = loginRequestSchema.safeParse(body);
    if (!parsed.success) {
      return HttpResponse.json(
        { detail: 'Invalid login payload' },
        { status: 422 }
      );
    }
    const record = users.get(parsed.data.email.toLowerCase());
    if (!record || record.password !== parsed.data.password) {
      return HttpResponse.json(
        { detail: 'Incorrect email or password' },
        { status: 401 }
      );
    }
    return HttpResponse.json({
      access_token: createMockAccessToken(record.user.id),
      token_type: 'bearer',
      expires_in: 3600,
    });
  }),
  http.get(`${apiBaseUrl}/auth/me`, async ({ request }) => {
    await delay(150);
    const accessToken = getAccessToken(request);
    const record = accessToken
      ? findMockUserByAccessToken(accessToken)
      : undefined;
    return record
      ? HttpResponse.json(record.user)
      : HttpResponse.json(
          { detail: 'Invalid or expired token' },
          { status: 401 }
        );
  }),
  http.post(`${apiBaseUrl}/auth/logout`, async ({ request }) => {
    await delay(100);
    const accessToken = getAccessToken(request);
    if (!accessToken || !findMockUserByAccessToken(accessToken)) {
      return HttpResponse.json(
        { detail: 'Invalid or expired token' },
        { status: 401 }
      );
    }
    return new HttpResponse(null, { status: 204 });
  }),
];
