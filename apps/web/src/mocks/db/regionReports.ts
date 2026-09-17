import type { RegionReportResponseDto } from '../../types/regionReport';

export const gyeongjuRegionReport: RegionReportResponseDto = {
  report_version: '2026-09-07',
  report_status: 'PROVISIONAL',
  generated_at: '2026-09-10T12:00:00Z',
  target: {
    region_id: '47130',
    province_name: '경상북도',
    region_name: '경주시',
    administrative_type: '시',
  },
  analysis_period: {
    start_ym: '202508',
    end_ym: '202607',
    month_count: 12,
  },
  summary: {
    diagnosis_status: 'GAP_FOUND',
    primary_gap_type: 'EXPERIENCE_TOURISM',
    one_line_review: {
      text: '경주시는 기존 관광 거점에 참여형 체험을 더해 실제 수요를 먼저 검증할 필요가 있습니다.',
      source: 'LLM',
      generated_at: '2026-09-10T12:00:00Z',
    },
    key_metrics: [
      {
        metric_code: 'MIN_BENCHMARK_SUPPLY_RATIO',
        content_type: 'EXPERIENCE_TOURISM',
        value: 0.6959,
        benchmark_region_id: '47110',
        benchmark_region_name: '포항시',
      },
      {
        metric_code: 'LOWER_BENCHMARK_COUNT',
        content_type: 'EXPERIENCE_TOURISM',
        value: 2,
        total_benchmark_count: 2,
      },
      {
        metric_code: 'SEARCHES_PER_PLACE',
        content_type: 'EXPERIENCE_TOURISM',
        value: 2117.5862,
        rank: 1,
        total_content_type_count: 6,
      },
    ],
  },
  evidence: {
    supply_density: {
      content_type: 'EXPERIENCE_TOURISM',
      target: {
        region_id: '47130',
        region_name: '경주시',
        value: 6.57,
      },
      benchmarks: [
        {
          region_id: '47110',
          region_name: '포항시',
          value: 9.44,
          target_to_benchmark_ratio: 0.6959,
        },
        {
          region_id: '44210',
          region_name: '서산시',
          value: 8.12,
          target_to_benchmark_ratio: 0.8091,
        },
      ],
    },
    searches_per_place: {
      metric_definition: '최근 12개월 내비게이션 목적지 검색량 ÷ 등록 장소 수',
      items: [
        {
          content_type: 'EXPERIENCE_TOURISM',
          navigation_search_count: 233684,
          supply_place_count: 110,
          searches_per_place: 2117.5862,
          rank: 1,
        },
        {
          content_type: 'ACCOMMODATION',
          navigation_search_count: 402072,
          supply_place_count: 264,
          searches_per_place: 1523,
          rank: 2,
        },
        {
          content_type: 'SHOPPING',
          navigation_search_count: 178464,
          supply_place_count: 143,
          searches_per_place: 1248,
          rank: 3,
        },
        {
          content_type: 'LEISURE_SPORTS',
          navigation_search_count: 65731,
          supply_place_count: 65,
          searches_per_place: 1011.25,
          rank: 4,
        },
        {
          content_type: 'CULTURE_TOURISM',
          navigation_search_count: 108914,
          supply_place_count: 118,
          searches_per_place: 923,
          rank: 5,
        },
        {
          content_type: 'FOOD',
          navigation_search_count: 481110,
          supply_place_count: 553,
          searches_per_place: 870,
          rank: 6,
        },
      ],
    },
  },
  category_overview: [
    {
      content_type: 'EXPERIENCE_TOURISM',
      signal_level: 'STRONG_GAP_CANDIDATE',
      supply_place_count: 87,
      composition_share: 0.1312,
      supply_density_per_100_km2: 6.57,
      lower_benchmark_count: 2,
      total_benchmark_count: 2,
      lowest_benchmark_supply_ratio: 0.6959,
      searches_per_place: 2117.5862,
      search_rank: 1,
    },
    {
      content_type: 'SHOPPING',
      signal_level: 'NEEDS_REVIEW',
      supply_place_count: 143,
      composition_share: 0.2157,
      supply_density_per_100_km2: 10.8,
      lower_benchmark_count: 1,
      total_benchmark_count: 2,
      lowest_benchmark_supply_ratio: 0.9,
      searches_per_place: 1248,
      search_rank: 3,
    },
    {
      content_type: 'ACCOMMODATION',
      signal_level: 'NO_CLEAR_GAP',
      supply_place_count: 264,
      composition_share: 0.3982,
      supply_density_per_100_km2: 19.93,
      lower_benchmark_count: 0,
      total_benchmark_count: 2,
      lowest_benchmark_supply_ratio: 1.08,
      searches_per_place: 1523,
      search_rank: 2,
    },
    {
      content_type: 'LEISURE_SPORTS',
      signal_level: 'NO_CLEAR_GAP',
      supply_place_count: 96,
      composition_share: 0.1448,
      supply_density_per_100_km2: 7.25,
      lower_benchmark_count: 0,
      total_benchmark_count: 2,
      lowest_benchmark_supply_ratio: 1.02,
      searches_per_place: 1002,
      search_rank: 4,
    },
    {
      content_type: 'CULTURE_TOURISM',
      signal_level: 'NO_CLEAR_GAP',
      supply_place_count: 118,
      composition_share: 0.178,
      supply_density_per_100_km2: 8.91,
      lower_benchmark_count: 0,
      total_benchmark_count: 2,
      lowest_benchmark_supply_ratio: 1.11,
      searches_per_place: 923,
      search_rank: 5,
    },
    {
      content_type: 'FOOD',
      signal_level: 'NO_CLEAR_GAP',
      supply_place_count: 553,
      composition_share: 0.52,
      supply_density_per_100_km2: 41.76,
      lower_benchmark_count: 1,
      total_benchmark_count: 2,
      lowest_benchmark_supply_ratio: null,
      searches_per_place: 870,
      search_rank: 6,
    },
  ],
  detailed_diagnoses: [
    {
      content_type: 'EXPERIENCE_TOURISM',
      signal_level: 'STRONG_GAP_CANDIDATE',
      judgement:
        '두 우수 지역보다 공급밀도가 낮고, 장소당 검색량은 6개 유형 중 가장 높아 추가 검증 우선순위가 높습니다.',
      quantitative_evidence: [
        {
          metric_code: 'MIN_BENCHMARK_SUPPLY_RATIO',
          value: 0.6959,
          comparisons: [
            {
              region_id: '47110',
              region_name: '포항시',
              benchmark_value: 9.44,
              target_to_benchmark_ratio: 0.6959,
            },
          ],
        },
        {
          metric_code: 'SEARCHES_PER_PLACE',
          value: 2117.5862,
          comparisons: [],
          rank: 1,
          total_count: 6,
        },
      ],
      applicability_insight:
        '기존 유적·야간 관광 동선에 예약형 소규모 체험을 붙여 반응을 확인할 수 있습니다.',
      case_ids: ['case-01', 'case-02'],
    },
    {
      content_type: 'SHOPPING',
      signal_level: 'NEEDS_REVIEW',
      judgement:
        '포항시보다 공급이 낮지만 서산시보다 높아 공급 부족 신호가 한쪽 비교 지역에서만 관찰됩니다.',
      quantitative_evidence: [
        {
          metric_code: 'MIN_BENCHMARK_SUPPLY_RATIO',
          value: 0.9,
          comparisons: [
            {
              region_id: '47110',
              region_name: '포항시',
              benchmark_value: 12,
              target_to_benchmark_ratio: 0.9,
            },
            {
              region_id: '44210',
              region_name: '서산시',
              benchmark_value: 9.56,
              target_to_benchmark_ratio: 1.13,
            },
          ],
        },
      ],
      applicability_insight:
        '관광 동선 안의 지역 상품 구매 전환을 별도로 확인한 뒤 공급 확대를 판단해야 합니다.',
      case_ids: ['case-03', 'missing-case'],
    },
  ],
  recommended_actions: [
    {
      order: 1,
      title: '기존 관광 거점에 체험 요소 덧붙이기',
      rationale:
        '주요 유적과 관광 동선에 참여형·예약형 프로그램을 결합하고 역사·가족·공예·야간·실내 체험 중 공백을 확인합니다.',
      evidence_texts: [
        '상대 공급: 우수 지역 2곳 모두보다 낮음',
        '가장 낮은 비교값: 0.70배',
      ],
      case_ids: ['case-01', 'case-03'],
    },
    {
      order: 2,
      title: '시설 없이 반복 프로그램으로 검증하기',
      rationale:
        '비수기·야간·가족 단위를 대상으로 소규모 프로그램을 운영해 참여 수요를 확인한 뒤 확대 여부를 결정합니다.',
      evidence_texts: ['장소당 검색량: 6개 유형 중 1위', '2,118회'],
      case_ids: ['case-02', 'case-04'],
    },
  ],
  benchmark_cases: [
    {
      case_id: 'case-01',
      benchmark_region_name: '포항시',
      title: '포항 스페이스워크',
      case_type: 'FACILITY',
      content_type: 'EXPERIENCE_TOURISM',
      period: '2021년~',
      operator: '포항시',
      summary: '도시 경관을 직접 걷고 체험하는 관람형 시설을 운영합니다.',
      applicability:
        '시설 자체보다 기존 관광 거점에서 체류 행동을 만드는 운영 원리를 참고합니다.',
      source_ids: ['source-01'],
    },
    {
      case_id: 'case-02',
      benchmark_region_name: '포항시',
      title: '포항 스틸아트페스티벌',
      case_type: 'PROGRAM',
      content_type: 'EXPERIENCE_TOURISM',
      period: '매년',
      operator: '포항시·포항문화재단',
      summary: '지역 산업 소재를 시민 참여형 문화 프로그램으로 확장했습니다.',
      applicability:
        '경주의 역사·공예 자원을 참여형 프로그램으로 번역하는 방식을 참고합니다.',
      source_ids: ['source-02'],
    },
    {
      case_id: 'case-03',
      benchmark_region_name: '서산시',
      title: '해미읍성 역사체험축제',
      case_type: 'PROGRAM',
      content_type: 'EXPERIENCE_TOURISM',
      period: '매년',
      operator: '서산시',
      summary: '역사 공간에서 반복 가능한 참여형 프로그램을 운영합니다.',
      applicability:
        '기존 역사 공간을 훼손하지 않으면서 체험 밀도를 높이는 원리를 참고합니다.',
      source_ids: ['source-03'],
    },
    {
      case_id: 'case-04',
      benchmark_region_name: '포항시',
      title: '포항국제불빛축제',
      case_type: 'PROGRAM',
      content_type: 'CULTURE_TOURISM',
      period: '매년',
      operator: '포항시·포항문화재단',
      summary: '야간 경관과 반복 프로그램을 결합해 방문 동기를 만듭니다.',
      applicability:
        '경주의 야간 관광 동선에서 시간대별 참여 수요를 검증할 때 참고합니다.',
      source_ids: ['source-02', 'missing-source'],
    },
  ],
  methodology: {
    benchmark_selection_rule:
      '인구·면적·관광 구조가 유사한 지역 중 관광 성과가 상대적으로 높은 지역을 선정합니다.',
    benchmark_selection_note:
      '구조적 유사성은 관광상품 구성이나 역사문화도시로서의 성격이 같다는 의미가 아닙니다.',
    supply_comparison_rule:
      '유형별 100㎢당 등록 장소 수를 대상 지역과 비교 지역 사이에서 비교합니다.',
    search_pressure_definition:
      '내비게이션 목적지 검색량을 같은 유형의 등록 장소 수로 나눈 탐색 지표입니다.',
    provisional_notice:
      '현재 보고서는 화면 개발용 예시 응답을 사용하는 잠정 분석입니다.',
    limitations: [
      '등록 장소 수는 실제 시설 수용 능력을 반영하지 않습니다.',
      '검색량은 실제 방문이나 미충족 수요와 다를 수 있습니다.',
      '공급 확대가 방문 증가로 이어지는 인과를 확인한 분석은 아닙니다.',
    ],
  },
  sources: [
    {
      source_id: 'source-01',
      title: '스페이스워크 안내',
      publisher: '포항시',
      url: 'https://www.pohang.go.kr',
      published_at: '2026-01-15',
    },
    {
      source_id: 'source-02',
      title: '포항문화재단 축제 안내',
      publisher: '포항문화재단',
      url: 'https://phcf.or.kr',
      published_at: '2026-05-01',
    },
    {
      source_id: 'source-03',
      title: '해미읍성축제 안내',
      publisher: '서산시',
      url: 'https://www.seosan.go.kr',
      published_at: '2026-04-12',
    },
  ],
};

export const pohangRegionReport: RegionReportResponseDto = {
  ...gyeongjuRegionReport,
  report_version: '2026-09-08',
  report_status: 'FINAL',
  target: {
    region_id: '47110',
    province_name: '경상북도',
    region_name: '포항시',
    administrative_type: '시',
  },
  summary: {
    diagnosis_status: 'NO_CLEAR_GAP',
    primary_gap_type: null,
    one_line_review: {
      text: '포항시는 비교 지역 대비 뚜렷한 대표 빈칸이 없어 유형별 변화 추이를 함께 살펴볼 필요가 있습니다.',
      source: 'TEMPLATE',
      generated_at: null,
    },
    key_metrics: [
      {
        metric_code: 'SUPPLY_PLACE_COUNT',
        content_type: 'CULTURE_TOURISM',
        value: 152,
      },
      {
        metric_code: 'SUPPLY_DENSITY_PER_100_KM2',
        content_type: 'CULTURE_TOURISM',
        value: 13.42,
      },
      {
        metric_code: 'SEARCHES_PER_PLACE',
        content_type: 'CULTURE_TOURISM',
        value: 1014.2,
        rank: 3,
        total_content_type_count: 6,
      },
      {
        metric_code: 'LOWER_BENCHMARK_COUNT',
        content_type: 'CULTURE_TOURISM',
        value: 0,
        total_benchmark_count: 2,
      },
    ],
  },
  category_overview: gyeongjuRegionReport.category_overview.map((item) => ({
    ...item,
    signal_level: 'NO_CLEAR_GAP',
  })),
  detailed_diagnoses: [],
  recommended_actions: [],
};

export const seosanInsufficientReport: RegionReportResponseDto = {
  ...gyeongjuRegionReport,
  report_version: '2026-09-09',
  report_status: 'FINAL',
  target: {
    region_id: '44210',
    province_name: '충청남도',
    region_name: '서산시',
    administrative_type: '시',
  },
  summary: {
    diagnosis_status: 'INSUFFICIENT_DATA',
    primary_gap_type: null,
    one_line_review: {
      text: '서산시는 현재 분석에 필요한 검색·공급 데이터가 충분하지 않아 관광 빈칸을 판단하기 어렵습니다.',
      source: 'TEMPLATE',
      generated_at: null,
    },
    key_metrics: [],
  },
  evidence: {
    supply_density: {
      content_type: 'UNKNOWN',
      target: { region_id: '44210', region_name: '서산시', value: 0 },
      benchmarks: [],
    },
    searches_per_place: {
      metric_definition: '분석 가능한 데이터가 충분하지 않습니다.',
      items: [],
    },
  },
  category_overview: [],
  detailed_diagnoses: [],
  recommended_actions: [],
  benchmark_cases: [],
  methodology: {
    ...gyeongjuRegionReport.methodology,
    provisional_notice: null,
    limitations: ['분석 기간에 필요한 검색·공급 데이터가 충분하지 않습니다.'],
  },
  sources: [],
};

export const regionReportsById: Record<string, RegionReportResponseDto> = {
  '47130': gyeongjuRegionReport,
  '47110': pohangRegionReport,
  '44210': seosanInsufficientReport,
};
