import { z } from 'zod';
import { ApiError } from '../types/api';
import type { RegionRef } from '../types/auth';
import type { ProvinceSummary } from '../types/regions';
import { apiClient } from './client';

const provincesSchema = z.object({
  items: z.array(
    z.object({
      province_name: z.string(),
      region_count: z.number().int(),
    })
  ),
  total: z.number().int(),
});

const regionsSchema = z.object({
  items: z.array(
    z.object({
      region_id: z.string().regex(/^\d{5}$/),
      province_name: z.string(),
      region_name: z.string(),
      administrative_type: z.enum(['시', '군', '자치구']),
    })
  ),
  total: z.number().int(),
});

export const fetchProvinces = async (): Promise<ProvinceSummary[]> => {
  const response = await apiClient.get<unknown>('/provinces');
  const result = provincesSchema.safeParse(response.data);
  if (!result.success) {
    throw new ApiError('시·도 목록을 확인하지 못했어요.', response.status);
  }
  return result.data.items;
};

export const fetchRegions = async (province: string): Promise<RegionRef[]> => {
  const response = await apiClient.get<unknown>('/regions', {
    params: { province, limit: 230 },
  });
  const result = regionsSchema.safeParse(response.data);
  if (!result.success) {
    throw new ApiError('시·군·구 목록을 확인하지 못했어요.', response.status);
  }
  return result.data.items;
};
