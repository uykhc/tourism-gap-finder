import type { RegionRef, UserResponse } from '../../types/auth';

export const users = new Map<string, UserResponse>();

// 회원가입 응답용 표본이며 지역 선택 목록을 대신하지 않는다.
export const signupRegions: RegionRef[] = [
  {
    region_id: '51210',
    province_name: '강원특별자치도',
    region_name: '속초시',
    administrative_type: '시',
  },
  {
    region_id: '47130',
    province_name: '경상북도',
    region_name: '경주시',
    administrative_type: '시',
  },
];
