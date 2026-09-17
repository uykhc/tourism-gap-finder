import { ApiError } from '../../types/api';
import { apiClient } from '../client';

export const logout = async (): Promise<void> => {
  const response = await apiClient.post<unknown>('/auth/logout');
  if (response.status !== 204) {
    throw new ApiError(
      '로그아웃을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.',
      response.status
    );
  }
};
