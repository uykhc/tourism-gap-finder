import { ApiError } from '../../types/api';
import type { ChangePasswordRequest } from '../../types/auth';
import { apiClient } from '../client';

export const changePassword = async (
  payload: ChangePasswordRequest
): Promise<void> => {
  const response = await apiClient.patch<unknown>(
    '/users/me/password',
    payload
  );
  if (response.status !== 204) {
    throw new ApiError(
      '비밀번호 변경 결과를 확인하지 못했어요. 다시 시도해 주세요.',
      response.status
    );
  }
};
