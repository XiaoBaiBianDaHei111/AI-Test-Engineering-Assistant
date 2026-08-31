// Typed API functions for failure analysis (Phase 7).

import { api } from './client';
import type { FailureAnalysis } from '../types';

export const failureAnalysisApi = {
  get: (runCaseId: number) => api.get<FailureAnalysis>(`/api/failure-analysis/${runCaseId}`),
  retry: (runCaseId: number) =>
    api.post<FailureAnalysis>('/api/failure-analysis', { run_case_id: runCaseId }),
  confirm: (analysisId: number) =>
    api.post<FailureAnalysis>(`/api/failure-analysis/${analysisId}/confirm`),
};
