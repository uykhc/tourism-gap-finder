import { useState } from 'react';
import { Navigate } from 'react-router';
import MyPageLayout from '../components/mypage/MyPageLayout';
import RegionSelector from '../components/region/RegionSelector';
import { Button } from '../components/ui/button';
import useAccessToken from '../hooks/useAccessToken';
import useCurrentUserQuery from '../hooks/useCurrentUserQuery';
import useUpdateInterestRegionMutation from '../hooks/useUpdateInterestRegionMutation';
import { ApiError } from '../types/api';

function MyPageRegion() {
  const accessToken = useAccessToken();
  const currentUserQuery = useCurrentUserQuery();
  const updateInterestMutation = useUpdateInterestRegionMutation();
  const [selectorOpen, setSelectorOpen] = useState(false);
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);
  const [feedback, setFeedback] = useState<{
    message: string;
    isError: boolean;
  } | null>(null);

  if (accessToken === null) {
    return (
      <Navigate to="/login" replace state={{ returnTo: '/mypage/region' }} />
    );
  }

  const currentRegion = currentUserQuery.data?.default_region ?? null;

  const toggleSelector = () => {
    setFeedback(null);
    setSelectedRegionId(null);
    setSelectorOpen((open) => !open);
  };

  const handleComplete = (regionId: string) => {
    setFeedback(null);
    updateInterestMutation.mutate(regionId, {
      onSuccess: (user) => {
        setSelectorOpen(false);
        setSelectedRegionId(null);
        setFeedback({
          message: user.default_region
            ? `관심 지역을 ${user.default_region.province_name} ${user.default_region.region_name}(으)로 변경했어요.`
            : '관심 지역을 변경했어요.',
          isError: false,
        });
      },
      onError: (error) => {
        setFeedback({
          message:
            error instanceof ApiError
              ? error.message
              : '관심 지역을 변경하지 못했어요. 다시 시도해 주세요.',
          isError: true,
        });
      },
    });
  };

  return (
    <MyPageLayout>
      <h1>관심 지역 설정</h1>
      <p className="text-body-small text-muted-foreground">
        로그인 시 기본으로 표시할 지역을 확인하고 변경할 수 있습니다.
      </p>
      <div className="flex flex-wrap items-center justify-between gap-3.5 rounded-xl border bg-card p-6">
        <div className="flex min-w-0 flex-col gap-1.5">
          <p className="text-label-small text-muted-foreground">
            현재 관심 지역
          </p>
          {currentUserQuery.isPending ? (
            <p className="text-heading text-muted-foreground">불러오는 중…</p>
          ) : currentUserQuery.isError ? (
            <div className="flex flex-wrap items-center gap-2.5">
              <p role="alert" className="text-body-small text-destructive">
                관심 지역 정보를 불러오지 못했어요.
              </p>
              <Button
                type="button"
                variant="outline"
                size="sm"
                onClick={() => void currentUserQuery.refetch()}
              >
                다시 시도
              </Button>
            </div>
          ) : (
            <p className="truncate text-heading text-foreground">
              {currentRegion
                ? `${currentRegion.province_name} ${currentRegion.region_name}`
                : '설정된 관심 지역이 없어요'}
            </p>
          )}
        </div>
        <Button
          type="button"
          variant={selectorOpen ? 'outline' : 'default'}
          disabled={
            currentUserQuery.isPending || updateInterestMutation.isPending
          }
          onClick={toggleSelector}
        >
          {selectorOpen ? '변경 취소' : '지역 변경'}
        </Button>
      </div>
      {feedback && (
        <p
          role={feedback.isError ? 'alert' : 'status'}
          className={
            feedback.isError
              ? 'text-body-small text-destructive'
              : 'text-body-small text-primary'
          }
        >
          {feedback.message}
        </p>
      )}
      {selectorOpen && (
        <RegionSelector
          value={selectedRegionId}
          onChange={setSelectedRegionId}
          onComplete={handleComplete}
          disabled={updateInterestMutation.isPending}
          completeLabel="관심 지역 변경하기"
        />
      )}
    </MyPageLayout>
  );
}

export default MyPageRegion;
