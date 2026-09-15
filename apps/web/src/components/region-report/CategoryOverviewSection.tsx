import {
  SIGNAL_LEVEL_LABEL,
  TOURISM_CONTENT_LABEL,
} from '../../constants/regionReport';
import type {
  CategoryOverviewItemDto,
  GapSignalLevel,
  TourismContentType,
} from '../../types/regionReport';
import { cn } from '../../utils/cn';
import {
  formatCount,
  formatDecimal,
  sortCategoryOverview,
} from '../../utils/regionReport';

const getSignalClassName = (signalLevel: GapSignalLevel) => {
  switch (signalLevel) {
    case 'STRONG_GAP_CANDIDATE':
      return 'bg-primary text-primary-foreground';
    case 'NEEDS_REVIEW':
      return 'bg-warning-muted text-warning-foreground';
    case 'NO_CLEAR_GAP':
    case 'UNKNOWN':
      return 'bg-muted text-muted-foreground';
  }
};

interface CategoryOverviewSectionProps {
  items: CategoryOverviewItemDto[];
  primaryGapType: TourismContentType | null;
}

function CategoryOverviewSection({
  items,
  primaryGapType,
}: CategoryOverviewSectionProps) {
  if (items.length === 0) return null;
  const sortedItems = sortCategoryOverview(items, primaryGapType);

  return (
    <section className="bg-muted/70">
      <div className="mx-auto flex w-full max-w-[1200px] flex-col gap-3 px-4 py-6 sm:px-8 lg:px-12">
        <h2>관광 유형 전체 진단</h2>
        <p className="text-body-small text-muted-foreground">
          선택 지역의 등록 공급과 검색 수요를 6개 유형에서 함께 확인합니다.
        </p>
        <div className="overflow-x-auto rounded-xl border bg-card">
          <table className="w-full min-w-[760px] border-collapse text-left text-body-small">
            <thead className="bg-muted/80 text-muted-foreground">
              <tr>
                <th scope="col" className="px-4 py-3 text-label-small">
                  관광 유형
                </th>
                <th scope="col" className="px-4 py-3 text-label-small">
                  등록 장소
                </th>
                <th scope="col" className="px-4 py-3 text-label-small">
                  공급밀도/100㎢
                </th>
                <th scope="col" className="px-4 py-3 text-label-small">
                  장소당 검색량
                </th>
                <th scope="col" className="px-4 py-3 text-label-small">
                  진단
                </th>
              </tr>
            </thead>
            <tbody>
              {sortedItems.map((item) => {
                const isPrimary = item.content_type === primaryGapType;
                return (
                  <tr
                    key={item.content_type}
                    className={cn('border-t', isPrimary && 'bg-secondary/70')}
                  >
                    <th
                      scope="row"
                      className={cn(
                        'px-4 py-3 text-label-small',
                        isPrimary ? 'text-primary' : 'text-foreground'
                      )}
                    >
                      {TOURISM_CONTENT_LABEL[item.content_type]}
                    </th>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatCount(item.supply_place_count)}개
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatDecimal(item.supply_density_per_100_km2)}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatCount(item.searches_per_place)}회
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          'inline-flex rounded-full px-2.5 py-1.5 text-label-small',
                          getSignalClassName(item.signal_level)
                        )}
                      >
                        {SIGNAL_LEVEL_LABEL[item.signal_level]}
                      </span>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>
    </section>
  );
}

export default CategoryOverviewSection;
