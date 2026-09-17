import { z } from 'zod';

export const passwordSchema = z
  .object({
    new_password: z
      .string()
      .min(8, '비밀번호는 8자 이상 입력해 주세요.')
      .max(128, '비밀번호는 128자 이하로 입력해 주세요.')
      .regex(/[A-Za-z]/, '비밀번호에 영문을 포함해 주세요.')
      .regex(/\d/, '비밀번호에 숫자를 포함해 주세요.'),
    new_password_confirm: z
      .string()
      .min(8, '비밀번호 확인을 8자 이상 입력해 주세요.')
      .max(128, '비밀번호 확인은 128자 이하로 입력해 주세요.'),
  })
  .refine((values) => values.new_password === values.new_password_confirm, {
    path: ['new_password_confirm'],
    message: '비밀번호가 일치하지 않습니다.',
  });

export type PasswordValues = z.infer<typeof passwordSchema>;

export const passwordDefaultValues: PasswordValues = {
  new_password: '',
  new_password_confirm: '',
};
