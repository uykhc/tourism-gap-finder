export const ADMINISTRATIVE_TYPES = [
  '시',
  '군',
  '자치구',
  '특별자치시',
] as const;

export type AdministrativeType = (typeof ADMINISTRATIVE_TYPES)[number];

export interface ProvinceSummary {
  province_name: string;
  region_count: number;
}
