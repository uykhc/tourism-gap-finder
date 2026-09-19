import { z } from 'zod';
import { ADMINISTRATIVE_TYPES } from '../../types/regions';

export const userResponseSchema = z.object({
  id: z.number().int(),
  email: z.string().email(),
  default_region: z
    .object({
      region_id: z.string().regex(/^\d{5}$/),
      province_name: z.string(),
      region_name: z.string(),
      administrative_type: z.enum(ADMINISTRATIVE_TYPES),
    })
    .nullable(),
  created_at: z.string(),
});
