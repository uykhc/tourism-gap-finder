import { http, HttpResponse, delay } from 'msw';
import { z } from 'zod';
import { apiBaseUrl } from '../../api/client';
import type { UserResponse } from '../../types/auth';
import { signupRegions, users } from '../db/users';

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
      signupRegions.find((item) => item.region_id === payload.default_region) ??
      null;
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
    // 가입 중복만 검증할 수 있도록 응답 정보만 저장하고 비밀번호는 저장하지 않는다.
    users.set(email, user);
    return HttpResponse.json(user, { status: 201 });
  }),
];
