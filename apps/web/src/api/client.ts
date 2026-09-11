import axios from 'axios';
import { ApiError, type ApiFieldError } from '../types/api';

export const apiBaseUrl = (
  import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000'
).replace(/\/+$/, '');

export const apiClient = axios.create({ baseURL: apiBaseUrl, timeout: 15000 });

const fieldMessages: Record<string, string> = {
  email: '이메일 형식을 확인해 주세요.',
  password: '비밀번호는 영문·숫자 포함 8~128자로 입력해 주세요.',
  password_confirm: '비밀번호 확인을 다시 입력해 주세요.',
  default_region: '관심 지역을 다시 선택하거나 건너뛰어 주세요.',
};

const getFieldErrors = (detail: unknown): ApiFieldError[] => {
  if (!Array.isArray(detail)) return [];
  return detail.flatMap((issue: unknown) => {
    if (typeof issue !== 'object' || issue === null || !('loc' in issue))
      return [];
    const location: unknown = issue.loc;
    if (!Array.isArray(location)) return [];
    const field: unknown = location[1];
    if (
      typeof field !== 'string' ||
      !Object.prototype.hasOwnProperty.call(fieldMessages, field)
    )
      return [];
    return [{ field, message: fieldMessages[field] }];
  });
};

apiClient.interceptors.response.use(
  (response) => response,
  (error: unknown) => {
    if (!axios.isAxiosError<unknown>(error)) {
      return Promise.reject(
        new ApiError('요청을 처리하지 못했어요. 다시 시도해 주세요.', undefined)
      );
    }
    const status = error.response?.status;
    const data = error.response?.data;
    const detail =
      typeof data === 'object' && data !== null && 'detail' in data
        ? data.detail
        : undefined;
    let message = '회원가입을 처리하지 못했어요. 잠시 후 다시 시도해 주세요.';
    let fields: ApiFieldError[] = [];
    if (status === 409) {
      message = '이미 가입된 이메일입니다.';
      fields = [{ field: 'email', message }];
    } else if (status === 422) {
      message =
        '입력 정보를 확인해 주세요. 문제가 계속되면 잠시 후 다시 시도해 주세요.';
      fields = getFieldErrors(detail);
      if (
        typeof detail === 'string' &&
        detail.startsWith('Unknown region_id:')
      ) {
        fields = [
          { field: 'default_region', message: fieldMessages.default_region },
        ];
      }
    } else if (status === undefined) {
      message =
        '가입 처리 결과를 확인하지 못했어요. 연결 상태를 확인해 주세요. 이미 가입되었다면 로그인해 주세요.';
    }
    // Axios 오류의 요청 config에 든 비밀번호를 UI와 mutation에 전달하지 않는다.
    return Promise.reject(new ApiError(message, status, fields));
  }
);
