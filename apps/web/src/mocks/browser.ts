import { setupWorker } from 'msw/browser';
import { authHandlers } from './handlers/auth';
import { regionHandlers } from './handlers/regions';

export const worker = setupWorker(...authHandlers, ...regionHandlers);
