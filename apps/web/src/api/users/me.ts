import { ApiError } from '../../types/api';
import type { UserResponse } from '../../types/auth';
import { userResponseSchema } from '../auth/userSchema';
import { apiClient } from '../client';

export const updateInterestRegion = async (
  regionId: string | null
): Promise<UserResponse> => {
  const response = await apiClient.patch<unknown>('/users/me', {
    default_region: regionId,
  });
  const result = userResponseSchema.safeParse(response.data);
  if (response.status !== 200 || !result.success) {
    throw new ApiError(
      '관심 지역 변경 결과를 확인하지 못했어요. 다시 시도해 주세요.',
      response.status
    );
  }
  return result.data;
};

export const deleteAccount = async (): Promise<void> => {
  const response = await apiClient.delete<unknown>('/users/me');
  if (response.status !== 204) {
    throw new ApiError(
      '회원 탈퇴를 처리하지 못했어요. 다시 시도해 주세요.',
      response.status
    );
  }
};
