import { z } from 'zod';

export const loginSchema = z.object({
  email: z.string().trim().email('이메일 형식을 확인해 주세요.'),
  password: z.string().min(1, '비밀번호를 입력해 주세요.'),
});

export type LoginValues = z.infer<typeof loginSchema>;

export const loginDefaultValues: LoginValues = {
  email: '',
  password: '',
};
