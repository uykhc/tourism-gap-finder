import { z } from 'zod';
import { ApiError } from '../../types/api';
import type { LoginRequest, TokenResponse } from '../../types/auth';
import { apiClient } from '../client';

const responseSchema = z.object({
  access_token: z.string(),
  token_type: z.string(),
  expires_in: z.number().int(),
});

export const login = async (payload: LoginRequest): Promise<TokenResponse> => {
  const response = await apiClient.post<unknown>('/auth/login', payload);
  const result = responseSchema.safeParse(response.data);
  if (response.status !== 200 || !result.success) {
    throw new ApiError(
      '로그인 처리 결과를 확인하지 못했어요. 잠시 후 다시 시도해 주세요.',
      response.status
    );
  }
  return result.data;
};
