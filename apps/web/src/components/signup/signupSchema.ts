import { z } from 'zod';

export const accountFields = ['email', 'password', 'password_confirm'] as const;

export const signupSchema = z
  .object({
    email: z.string().trim().email('이메일 형식을 확인해 주세요.'),
    password: z
      .string()
      .min(8, '비밀번호는 8자 이상 입력해 주세요.')
      .max(128, '비밀번호는 128자 이하로 입력해 주세요.')
      .regex(/[A-Za-z]/, '비밀번호에 영문을 포함해 주세요.')
      .regex(/\d/, '비밀번호에 숫자를 포함해 주세요.'),
    password_confirm: z
      .string()
      .min(8, '비밀번호 확인을 8자 이상 입력해 주세요.')
      .max(128, '비밀번호 확인은 128자 이하로 입력해 주세요.'),
    default_region: z
      .string()
      .regex(/^\d{5}$/, '관심 지역을 다시 선택해 주세요.')
      .nullable(),
  })
  .refine((values) => values.password === values.password_confirm, {
    path: ['password_confirm'],
    message: '비밀번호가 일치하지 않습니다.',
  });

export type SignUpValues = z.infer<typeof signupSchema>;

export const signupDefaultValues: SignUpValues = {
  email: '',
  password: '',
  password_confirm: '',
  default_region: null,
};
