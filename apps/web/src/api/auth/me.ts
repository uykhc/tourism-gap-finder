import { ApiError } from '../../types/api';
import type { UserResponse } from '../../types/auth';
import { apiClient } from '../client';
import { userResponseSchema } from './userSchema';

export const fetchCurrentUser = async (): Promise<UserResponse> => {
  const response = await apiClient.get<unknown>('/auth/me');
  const result = userResponseSchema.safeParse(response.data);
  if (response.status !== 200 || !result.success) {
    throw new ApiError(
      '사용자 정보를 확인하지 못했어요. 다시 로그인해 주세요.',
      response.status
    );
  }
  return result.data;
};
