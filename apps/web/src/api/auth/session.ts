const ACCESS_TOKEN_KEY = 'hankkeut_access_token';
const ACCESS_TOKEN_CHANGE_EVENT = 'hankkeut-access-token-change';

const emitAccessTokenChange = (): void => {
  window.dispatchEvent(new Event(ACCESS_TOKEN_CHANGE_EVENT));
};

export const getAccessToken = (): string | null => {
  if (typeof window === 'undefined') return null;
  return window.sessionStorage.getItem(ACCESS_TOKEN_KEY);
};

export const setAccessToken = (accessToken: string): void => {
  window.sessionStorage.setItem(ACCESS_TOKEN_KEY, accessToken);
  emitAccessTokenChange();
};

export const clearAccessToken = (): void => {
  if (typeof window === 'undefined') return;
  if (window.sessionStorage.getItem(ACCESS_TOKEN_KEY) === null) return;
  window.sessionStorage.removeItem(ACCESS_TOKEN_KEY);
  emitAccessTokenChange();
};

export const subscribeAccessToken = (
  onStoreChange: () => void
): (() => void) => {
  window.addEventListener(ACCESS_TOKEN_CHANGE_EVENT, onStoreChange);
  window.addEventListener('storage', onStoreChange);
  return () => {
    window.removeEventListener(ACCESS_TOKEN_CHANGE_EVENT, onStoreChange);
    window.removeEventListener('storage', onStoreChange);
  };
};
