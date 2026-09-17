import { ApiError } from '../../types/api';
import type { SignUpRequest, UserResponse } from '../../types/auth';
import { apiClient } from '../client';
import { userResponseSchema } from './userSchema';

export const signUp = async (payload: SignUpRequest): Promise<UserResponse> => {
  // 동의 필드 삭제 후 계약이다. 현재 서버의 필드 삭제 반영이 필요하다.
  const response = await apiClient.post<unknown>('/auth/signup', payload);
  const result = userResponseSchema.safeParse(response.data);
  if (response.status !== 201 || !result.success) {
    throw new ApiError(
      '가입 처리 결과를 확인하지 못했어요. 이미 가입되었다면 로그인해 주세요.',
      response.status
    );
  }
  return result.data;
};
