export interface SignUpRequest {
  email: string;
  password: string;
  password_confirm: string;
  default_region: string | null;
}

export interface RegionRef {
  region_id: string;
  province_name: string;
  region_name: string;
  administrative_type: '시' | '군' | '자치구';
}

export interface UserResponse {
  id: number;
  email: string;
  default_region: RegionRef | null;
  created_at: string;
}
