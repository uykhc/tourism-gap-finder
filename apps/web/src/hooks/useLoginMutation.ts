import { useMutation } from '@tanstack/react-query';
import { login } from '../api/auth/login';

export default function useLoginMutation() {
  return useMutation({
    mutationFn: login,
    retry: false,
    // 비밀번호를 포함한 mutation 변수를 비활성 캐시에 보관하지 않는다.
    gcTime: 0,
  });
}
