import { z } from 'zod';
import { ApiError } from '../../types/api';
import type { RegionReportResponseDto } from '../../types/regionReport';
import { ADMINISTRATIVE_TYPES } from '../../types/regions';
import { apiClient } from '../client';

const unknownEnumValue = (enumName: string) =>
  z.string().transform((value) => {
    console.error(`[region-report] 알 수 없는 ${enumName}: ${value}`);
    return 'UNKNOWN' as const;
  });

const reportStatusSchema = z
  .enum(['FINAL', 'PROVISIONAL'])
  .or(unknownEnumValue('report_status'));

const diagnosisStatusSchema = z
  .enum(['GAP_FOUND', 'NO_CLEAR_GAP', 'INSUFFICIENT_DATA'])
  .or(unknownEnumValue('diagnosis_status'));

const contentTypeSchema = z
  .enum([
    'EXPERIENCE_TOURISM',
    'ACCOMMODATION',
    'SHOPPING',
    'LEISURE_SPORTS',
    'CULTURE_TOURISM',
    'FOOD',
  ])
  .or(unknownEnumValue('content_type'));

const signalLevelSchema = z
  .enum(['STRONG_GAP_CANDIDATE', 'NEEDS_REVIEW', 'NO_CLEAR_GAP'])
  .or(unknownEnumValue('signal_level'));

const oneLineReviewSourceSchema = z
  .enum(['LLM', 'TEMPLATE'])
  .or(unknownEnumValue('one_line_review.source'));

const caseTypeSchema = z
  .enum(['FACILITY', 'PROGRAM'])
  .or(unknownEnumValue('case_type'));

const knownMetricCodes = [
  'MIN_BENCHMARK_SUPPLY_RATIO',
  'LOWER_BENCHMARK_COUNT',
  'SEARCHES_PER_PLACE',
  'SUPPLY_PLACE_COUNT',
  'SUPPLY_DENSITY_PER_100_KM2',
] as const;

const keyMetricCodeSchema = z
  .enum(knownMetricCodes)
  .or(unknownEnumValue('metric_code'));

const keyMetricBaseShape = {
  content_type: contentTypeSchema,
  value: z.number().finite(),
};

const unknownMetricCodeSchema = z
  .string()
  .refine(
    (value) => !knownMetricCodes.some((knownCode) => knownCode === value),
    '알려진 지표 코드는 해당 지표 계약을 따라야 합니다.'
  )
  .transform((value) => {
    console.error(`[region-report] 알 수 없는 metric_code: ${value}`);
    return 'UNKNOWN' as const;
  });

const keyMetricSchema = z.union([
  z.object({
    ...keyMetricBaseShape,
    metric_code: z.literal('MIN_BENCHMARK_SUPPLY_RATIO'),
    benchmark_region_id: z.string(),
    benchmark_region_name: z.string(),
  }),
  z.object({
    ...keyMetricBaseShape,
    metric_code: z.literal('LOWER_BENCHMARK_COUNT'),
    total_benchmark_count: z.number().int().nonnegative(),
  }),
  z.object({
    ...keyMetricBaseShape,
    metric_code: z.literal('SEARCHES_PER_PLACE'),
    rank: z.number().int().positive(),
    total_content_type_count: z.number().int().positive(),
  }),
  z.object({
    ...keyMetricBaseShape,
    metric_code: z.literal('SUPPLY_PLACE_COUNT'),
  }),
  z.object({
    ...keyMetricBaseShape,
    metric_code: z.literal('SUPPLY_DENSITY_PER_100_KM2'),
  }),
  z.object({
    ...keyMetricBaseShape,
    metric_code: unknownMetricCodeSchema,
  }),
]);

const regionMetricSchema = z.object({
  region_id: z.string(),
  region_name: z.string(),
  value: z.number().finite(),
  // The target itself has no comparison baseline, so the API represents its
  // ratio as null. Benchmark rows contain a numeric ratio.
  target_to_benchmark_ratio: z.number().finite().nullable().optional(),
});

const searchMetricSchema = z.object({
  content_type: contentTypeSchema,
  navigation_search_count: z.number().finite(),
  supply_place_count: z.number().finite(),
  searches_per_place: z.number().finite(),
  rank: z.number().int().positive(),
});

const categoryOverviewSchema = z.object({
  content_type: contentTypeSchema,
  signal_level: signalLevelSchema,
  supply_place_count: z.number().finite(),
  composition_share: z.number().finite(),
  supply_density_per_100_km2: z.number().finite(),
  lower_benchmark_count: z.number().int().nonnegative(),
  total_benchmark_count: z.number().int().nonnegative(),
  lowest_benchmark_supply_ratio: z.number().finite().nullable(),
  searches_per_place: z.number().finite(),
  search_rank: z.number().int().positive(),
});

const quantitativeEvidenceSchema = z.object({
  metric_code: keyMetricCodeSchema,
  value: z.number().finite(),
  comparisons: z.array(
    z.object({
      region_id: z.string(),
      region_name: z.string(),
      benchmark_value: z.number().finite(),
      target_to_benchmark_ratio: z.number().finite().nullable(),
    })
  ),
  rank: z.number().int().positive().nullable(),
  total_count: z.number().int().positive().nullable(),
});

const regionReportSchema = z.object({
  report_version: z.string(),
  report_status: reportStatusSchema,
  generated_at: z.string(),
  target: z.object({
    region_id: z.string().regex(/^\d{5}$/),
    province_name: z.string(),
    region_name: z.string(),
    administrative_type: z
      .enum(ADMINISTRATIVE_TYPES)
      .or(unknownEnumValue('administrative_type')),
  }),
  analysis_period: z.object({
    start_ym: z.string().regex(/^\d{6}$/),
    end_ym: z.string().regex(/^\d{6}$/),
    month_count: z.number().int().nonnegative(),
  }),
  summary: z
    .object({
      diagnosis_status: diagnosisStatusSchema,
      primary_gap_type: contentTypeSchema.nullable(),
      one_line_review: z.object({
        text: z.string(),
        source: oneLineReviewSourceSchema,
        generated_at: z.string().nullable(),
      }),
      key_metrics: z.array(keyMetricSchema),
    })
    .superRefine((summary, context) => {
      if (
        summary.diagnosis_status === 'GAP_FOUND' &&
        summary.primary_gap_type === null
      ) {
        context.addIssue({
          code: 'custom',
          path: ['primary_gap_type'],
          message: 'GAP_FOUND에는 대표 관광 유형이 필요합니다.',
        });
      }
      if (
        (summary.diagnosis_status === 'NO_CLEAR_GAP' ||
          summary.diagnosis_status === 'INSUFFICIENT_DATA') &&
        summary.primary_gap_type !== null
      ) {
        context.addIssue({
          code: 'custom',
          path: ['primary_gap_type'],
          message: '대표 관광 유형이 없어야 하는 분석 상태입니다.',
        });
      }
    }),
  evidence: z.object({
    supply_density: z.object({
      content_type: contentTypeSchema,
      target: regionMetricSchema,
      benchmarks: z.array(regionMetricSchema),
    }),
    searches_per_place: z.object({
      metric_definition: z.string(),
      items: z.array(searchMetricSchema),
    }),
  }),
  category_overview: z.array(categoryOverviewSchema),
  detailed_diagnoses: z.array(
    z.object({
      content_type: contentTypeSchema,
      signal_level: signalLevelSchema,
      judgement: z.string(),
      insight: z.string(),
      quantitative_evidence: z.array(quantitativeEvidenceSchema),
      applicability_insight: z.string(),
      case_ids: z.array(z.string()),
    })
  ),
  recommended_actions: z.array(
    z.object({
      order: z.number().int().positive(),
      title: z.string(),
      rationale: z.string(),
      evidence_texts: z.array(z.string()),
      case_ids: z.array(z.string()),
    })
  ),
  benchmark_cases: z.array(
    z.object({
      case_id: z.string(),
      benchmark_region_name: z.string(),
      title: z.string(),
      case_type: caseTypeSchema,
      content_type: contentTypeSchema,
      period: z.string(),
      operator: z.string(),
      summary: z.string(),
      applicability: z.string(),
      source_ids: z.array(z.string()),
    })
  ),
  methodology: z.object({
    benchmark_selection_rule: z.string(),
    benchmark_selection_note: z.string(),
    supply_comparison_rule: z.string(),
    search_pressure_definition: z.string(),
    provisional_notice: z.string().nullable(),
    limitations: z.array(z.string()),
  }),
  sources: z.array(
    z.object({
      source_id: z.string(),
      title: z.string(),
      publisher: z.string(),
      url: z.string().url(),
      published_at: z.string(),
    })
  ),
});

export const fetchRegionReport = async (
  regionId: string
): Promise<RegionReportResponseDto> => {
  const response = await apiClient.get<unknown>(`/regions/${regionId}/report`);
  const result = regionReportSchema.safeParse(response.data);
  if (!result.success) {
    console.error('[region-report] 응답 계약 검증 실패', result.error.issues);
    throw new ApiError(
      '보고서 데이터를 확인하지 못했어요. 잠시 후 다시 시도해 주세요.',
      response.status
    );
  }
  return result.data;
};
