import { useState } from 'react';
import { useNavigate } from 'react-router';
import RegionSelector from '../components/region/RegionSelector';

function Home() {
  const navigate = useNavigate();
  const [selectedRegionId, setSelectedRegionId] = useState<string | null>(null);

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
