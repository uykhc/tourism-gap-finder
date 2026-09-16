import type { UserResponse } from '../../types/auth';

export interface MockUserRecord {
  user: UserResponse;
  password: string;
}

const MOCK_USERS_KEY = 'hankkeut_mock_users';

const loadMockUsers = (): Map<string, MockUserRecord> => {
  try {
    const stored = window.sessionStorage.getItem(MOCK_USERS_KEY);
    if (!stored) return new Map();
    const entries: unknown = JSON.parse(stored);
    if (!Array.isArray(entries)) return new Map();
    return new Map(entries as [string, MockUserRecord][]);
  } catch {
    return new Map();
  }
};

export const users = loadMockUsers();

export const saveMockUsers = (): void => {
  // 새로고침 뒤에도 개발용 로그인 흐름을 재현하기 위한 MSW 전용 저장소다.
  window.sessionStorage.setItem(
    MOCK_USERS_KEY,
    JSON.stringify(Array.from(users.entries()))
  );
};

export const createMockAccessToken = (userId: number): string =>
  `mock-access-token-${userId}`;

export const findMockUserByAccessToken = (
  accessToken: string
): MockUserRecord | undefined =>
  Array.from(users.values()).find(
    ({ user }) => createMockAccessToken(user.id) === accessToken
  );
