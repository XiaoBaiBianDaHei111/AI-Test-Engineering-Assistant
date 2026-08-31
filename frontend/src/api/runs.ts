// Typed API functions for execution (runs) endpoints.

import { api } from './client';
import type { RunConfig, RunCreateResponse, TestRun, TestRunCase } from '../types';

export interface RunCreateInput {
  project_id: number;
  test_case_ids?: number[];
  api_case_ids?: number[];
  config: RunConfig;
}

export const runsApi = {
  create: (data: RunCreateInput) => api.post<RunCreateResponse>('/api/runs', data),
  list: (projectId: number) => api.get<TestRun[]>(`/api/runs?project_id=${projectId}`),
  get: (runId: number) => api.get<TestRun>(`/api/runs/${runId}`),
  cancel: (runId: number) => api.post<TestRun>(`/api/runs/${runId}/cancel`),
  getCase: (runId: number, caseId: number) =>
    api.get<TestRunCase>(`/api/runs/${runId}/cases/${caseId}`),
  getScript: (runId: number, caseId: number) =>
    api.getText(`/api/runs/${runId}/cases/${caseId}/script`),
  putScript: (runId: number, caseId: number, script: string) =>
    api.putText(`/api/runs/${runId}/cases/${caseId}/script`, script),
  rerun: (runId: number, caseId: number) =>
    api.post<TestRunCase>(`/api/runs/${runId}/cases/${caseId}/rerun`),
};
