import { Link } from 'react-router';
import type { UserResponse } from '../../types/auth';
import { Button } from '../ui/button';

export default function SignUpCompleteStep({ user }: { user: UserResponse }) {
  const region = user.default_region;
  return (
    <div className="mx-auto flex w-full max-w-[760px] flex-col items-center gap-6 rounded-xl border bg-card px-6 py-8 sm:px-9">
      <div
        aria-hidden="true"
        className="flex size-[72px] items-center justify-center rounded-full bg-primary text-heading text-primary-foreground"
      >
        ✓
      </div>
      <h1 id="signup-title" tabIndex={-1} className="text-center outline-none">
        회원가입이 완료되었어요
      </h1>
      <p className="w-full text-muted-foreground">
        韓끗에서 우리 지역의 관광 빈칸을 찾아보세요.
      </p>
      <section
        aria-label="관심 지역"
        className="flex w-full flex-col gap-1.5 rounded-lg border bg-secondary p-5"
      >
        <p className="text-body-small text-primary">관심 지역</p>
        <h2>
          {region
            ? `${region.province_name} ${region.region_name}`
            : '아직 설정하지 않음'}
        </h2>
        <p className="text-body-small text-muted-foreground">
          지역 설정을 건너뛴 경우 ‘아직 설정하지 않음’으로 표시됩니다.
        </p>
      </section>
      <Button asChild className="h-[52px] w-full">
        <Link to={region ? `/dashboard/${region.region_id}` : '/'}>
          韓끗 시작하기
        </Link>
      </Button>
      <p className="text-center text-body-small text-muted-foreground">
        관심 지역은 마이페이지에서 언제든 설정하거나 변경할 수 있어요.
      </p>
    </div>
  );
}
