import { SIMILAR_REGION_SELECTION_DESCRIPTION } from '../../constants/regionReport';
import type { SimilarRegionDto } from '../../types/regionReport';
import { formatTwoDigitOrder } from '../../utils/regionReport';
import InfoHoverCard from './InfoHoverCard';

interface SimilarRegionsSectionProps {
  regions: SimilarRegionDto[];
}

function SimilarRegionsSection({ regions }: SimilarRegionsSectionProps) {
  if (regions.length === 0) return null;

  // 화면에는 상위 3곳만 카드로 보여준다. 백엔드는 구조 유사도 상위
  // 10곳까지 내려줄 수 있다.
  const topRegions = [...regions]
    .sort((left, right) => left.rank - right.rank)
    .slice(0, 3);

  return (
    <section className="bg-background">
      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-3 px-4 py-6 sm:px-8 lg:px-12">
        <h2 className="flex items-center gap-1">
          선정된 유사 지역
          <InfoHoverCard
            label="선정된 유사 지역"
            description={SIMILAR_REGION_SELECTION_DESCRIPTION}
          />
        </h2>
        <p className="text-body-small text-muted-foreground">
          인구·면적·관광 구조가 비슷한 지역을 유사도 순으로 표시합니다.
        </p>
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-3">
          {topRegions.map((region) => (
            <article
              key={region.region_id}
              className="flex items-center gap-2 rounded-[10px] border bg-muted/50 p-3.5"
            >
              <span className="text-label-small text-primary">
                {formatTwoDigitOrder(region.rank)}
              </span>
              <span className="text-body-strong">{region.region_name}</span>
              <span className="ml-auto text-body-small text-primary">
                유사도 {(region.similarity * 100).toFixed(1)}%
              </span>
            </article>
          ))}
        </div>
      </div>
    </section>
  );
}

export default SimilarRegionsSection;
