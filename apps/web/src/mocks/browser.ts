import { setupWorker } from 'msw/browser';
import { authHandlers } from './handlers/auth';
import { regionReportHandlers } from './handlers/regionReports';
import { regionHandlers } from './handlers/regions';
import { userHandlers } from './handlers/users';

export const worker = setupWorker(
  ...authHandlers,
  ...regionHandlers,
  ...regionReportHandlers,
  ...userHandlers
);
