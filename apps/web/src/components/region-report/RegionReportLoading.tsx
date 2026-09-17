import { Skeleton } from '../ui/skeleton';

function RegionReportLoading() {
  return (
    <div aria-live="polite" aria-busy="true">
      <span className="sr-only">지역 관광 보고서를 불러오는 중입니다.</span>
      <section className="bg-secondary">
        <div className="mx-auto grid w-full max-w-[1200px] gap-6 px-4 py-8 sm:px-8 lg:grid-cols-[1fr_280px] lg:px-12">
          <div className="flex flex-col gap-3">
            <Skeleton className="h-5 w-52" />
            <Skeleton className="h-8 w-full max-w-2xl" />
            <Skeleton className="h-8 w-36 rounded-full" />
          </div>
          <Skeleton className="h-40 w-full rounded-xl" />
        </div>
      </section>
      <section className="mx-auto flex w-full max-w-[1200px] flex-col gap-4 px-4 py-6 sm:px-8 lg:px-12">
        <Skeleton className="h-6 w-28" />
        <div className="grid grid-cols-1 gap-4 md:grid-cols-3">
          <Skeleton className="h-26" />
          <Skeleton className="h-26" />
          <Skeleton className="h-26" />
        </div>
      </section>
      <section className="bg-card">
        <div className="mx-auto grid w-full max-w-[1200px] grid-cols-1 gap-4 px-4 py-7 sm:px-8 lg:grid-cols-2 lg:px-12">
          <Skeleton className="h-72" />
          <Skeleton className="h-72" />
        </div>
      </section>
    </div>
  );
}

export default RegionReportLoading;
