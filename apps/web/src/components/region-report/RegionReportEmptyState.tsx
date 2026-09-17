interface RegionReportEmptyStateProps {
  limitations: string[];
}

function RegionReportEmptyState({ limitations }: RegionReportEmptyStateProps) {
  return (
    <section className="bg-background">
      <div className="mx-auto w-full max-w-[1200px] px-4 py-7 sm:px-8 lg:px-12">
        <div className="flex flex-col gap-3 rounded-xl border bg-card p-5">
          <h2>현재는 세부 진단을 제공하기 어려워요</h2>
          <p className="text-muted-foreground">
            분석 데이터가 보완되면 핵심 지표와 유형별 진단을 확인할 수 있습니다.
          </p>
          {limitations.length > 0 && (
            <ul className="list-disc space-y-1 pl-5 text-body-small text-muted-foreground">
              {limitations.map((limitation) => (
                <li key={limitation}>{limitation}</li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </section>
  );
}

export default RegionReportEmptyState;
