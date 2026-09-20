import { useState } from 'react';
import { useLocation, useNavigate, useParams } from 'react-router';
import CasesAndMethodologySection from '../components/region-report/CasesAndMethodologySection';
import DetailedDiagnosisSection from '../components/region-report/DetailedDiagnosisSection';
import RecommendedActionSection from '../components/region-report/RecommendedActionSection';
import RegionChangeDialog from '../components/region-report/RegionChangeDialog';
import RegionReportEmptyState from '../components/region-report/RegionReportEmptyState';
import RegionReportError from '../components/region-report/RegionReportError';
import RegionReportLoading from '../components/region-report/RegionReportLoading';
import ReportHero from '../components/region-report/ReportHero';
import SimilarRegionsSection from '../components/region-report/SimilarRegionsSection';
import TourismTypeComparisonSection from '../components/region-report/TourismTypeComparisonSection';
import useAccessToken from '../hooks/useAccessToken';
import useCurrentUserQuery from '../hooks/useCurrentUserQuery';
import useRegionReportQuery from '../hooks/useRegionReportQuery';
import useUpdateInterestRegionMutation from '../hooks/useUpdateInterestRegionMutation';
import { ApiError } from '../types/api';

function RegionDashboard() {
  const { regionCode } = useParams();
  const location = useLocation();
  const navigate = useNavigate();
  const [regionDialogOpen, setRegionDialogOpen] = useState(false);
  const [interestFeedback, setInterestFeedback] = useState<{
    message: string;
    isError: boolean;
  } | null>(null);
  const validRegionId =
    regionCode && /^\d{5}$/.test(regionCode) ? regionCode : null;
  const reportQuery = useRegionReportQuery(validRegionId);
  const accessToken = useAccessToken();
  const currentUserQuery = useCurrentUserQuery();
  const updateInterestMutation = useUpdateInterestRegionMutation();

  if (validRegionId === null) {
    return (
      <>
        <RegionReportError
          status={404}
          message="지역 코드를 확인하거나 다른 지역을 선택해 주세요."
          onRetry={() => undefined}
          onOpenRegionChange={() => setRegionDialogOpen(true)}
        />
        <RegionChangeDialog
          open={regionDialogOpen}
          onOpenChange={setRegionDialogOpen}
        />
      </>
    );
  }

  if (reportQuery.isPending) return <RegionReportLoading />;

  if (reportQuery.isError) {
    const status =
      reportQuery.error instanceof ApiError
        ? reportQuery.error.status
        : undefined;
    const errorMessage =
      status === 404
        ? '존재하지 않는 지역이거나 아직 생성된 보고서가 없습니다.'
        : reportQuery.error.message;
    return (
      <>
        <RegionReportError
          status={status}
          message={errorMessage}
          onRetry={() => void reportQuery.refetch()}
          onOpenRegionChange={() => setRegionDialogOpen(true)}
        />
        <RegionChangeDialog
          open={regionDialogOpen}
          onOpenChange={setRegionDialogOpen}
        />
      </>
    );
  }

  const report = reportQuery.data;
  const isInsufficient =
    report.summary.diagnosis_status === 'INSUFFICIENT_DATA';
  const isInterested =
    accessToken !== null &&
    currentUserQuery.data?.default_region?.region_id ===
      report.target.region_id;

  const handleToggleInterest = () => {
    setInterestFeedback(null);
    if (!accessToken) {
      navigate('/login', {
        state: {
          returnTo: `${location.pathname}${location.search}${location.hash}`,
        },
      });
      return;
    }
    if (!currentUserQuery.data) {
      setInterestFeedback({
        message: '사용자 정보를 확인하지 못했어요. 잠시 후 다시 시도해 주세요.',
        isError: true,
      });
      void currentUserQuery.refetch();
      return;
    }

    const nextRegionId = isInterested ? null : report.target.region_id;
    updateInterestMutation.mutate(nextRegionId, {
      onSuccess: () => {
        setInterestFeedback({
          message: isInterested
            ? '관심 지역에서 해제했어요.'
            : `${report.target.region_name}를 관심 지역으로 설정했어요.`,
          isError: false,
        });
      },
      onError: (error) => {
        setInterestFeedback({
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
    <div className="flex flex-1 flex-col">
      <ReportHero
        target={report.target}
        analysisPeriod={report.analysis_period}
        summary={report.summary}
        interestAction={{
          isInterested,
          isPending:
            currentUserQuery.isFetching || updateInterestMutation.isPending,
          onToggleInterest: handleToggleInterest,
          feedback: interestFeedback,
        }}
        onOpenRegionChange={() => setRegionDialogOpen(true)}
      />

      {isInsufficient ? (
        <RegionReportEmptyState limitations={report.methodology.limitations} />
      ) : (
        <>
          <SimilarRegionsSection regions={report.similar_regions} />
          <TourismTypeComparisonSection
            comparisons={report.tourism_type_comparisons}
            primaryGapType={report.summary.primary_gap_type}
          />
          <DetailedDiagnosisSection diagnoses={report.detailed_diagnoses} />
          <RecommendedActionSection
            actions={report.recommended_actions}
            cases={report.benchmark_cases}
          />
        </>
      )}

      <CasesAndMethodologySection
        cases={report.benchmark_cases}
        methodology={report.methodology}
        sources={report.sources}
      />
      <RegionChangeDialog
        open={regionDialogOpen}
        onOpenChange={setRegionDialogOpen}
      />
    </div>
  );
}

export default RegionDashboard;
