import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router';
import RegionSelector from '../components/region/RegionSelector';
import useAccessToken from '../hooks/useAccessToken';
import useCurrentUserQuery from '../hooks/useCurrentUserQuery';

function Home() {
  const navigate = useNavigate();
  const accessToken = useAccessToken();
  const currentUserQuery = useCurrentUserQuery();
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);

  const defaultRegionId =
    currentUserQuery.data?.default_region?.region_id ?? null;
  // 로그인 상태에서 사용자 정보를 불러오는 동안은 랜딩 화면이 잠깐 보였다가
  // 대시보드로 튕기는 깜빡임을 피하기 위해 아무것도 렌더링하지 않는다.
  const isResolvingDestination =
    accessToken !== null && currentUserQuery.isPending;

  useEffect(() => {
    if (accessToken !== null && defaultRegionId) {
      navigate(`/dashboard/${defaultRegionId}`, { replace: true });
    }
  }, [accessToken, defaultRegionId, navigate]);

  if (isResolvingDestination || (accessToken !== null && defaultRegionId)) {
    return null;
  }

  return (
    <div className="flex flex-1 flex-col items-center justify-center gap-6 bg-muted px-4 py-10 sm:px-8 lg:px-12">
      <div className="flex w-full max-w-300 flex-col items-center gap-2 text-center">
        <h1>우리 지역 관광에는 무엇이 부족할까?</h1>
        <p className="text-body-strong text-muted-foreground">
          한국관광공사 OpenAPI 데이터를 바탕으로 시·군·구의 관광자원 구조와
          보완이 필요한 콘텐츠를 찾아보세요.
        </p>
      </div>
      <div className="w-full max-w-300">
        <RegionSelector
          value={selectedRegionId}
          onChange={setSelectedRegionId}
          onComplete={(regionId) => navigate(`/dashboard/${regionId}`)}
          completeLabel="이 지역 보고서 보기"
        />
      </div>
    </div>
  );
}

export default Home;
