import { useSyncExternalStore } from 'react';
import { getAccessToken, subscribeAccessToken } from '../api/auth/session';

export default function useAccessToken() {
  return useSyncExternalStore(subscribeAccessToken, getAccessToken, () => null);
}
