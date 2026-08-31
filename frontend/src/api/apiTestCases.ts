// Typed API functions for API test cases (Phase 9).

import { api } from './client';
import type { ApiTestCase } from '../types';

export interface ApiTestCaseCreateInput {
  name: string;
  method: string;
  url: string;
  headers?: Record<string, string>;
  body?: Record<string, unknown> | null;
  assertions: { type: string; expected?: unknown; path?: string; expected_ms?: number; name?: string }[];
  requirement_id?: number | null;
  status?: string;
}

export const apiTestCasesApi = {
  list: (projectId: number) => api.get<ApiTestCase[]>(`/api/projects/${projectId}/api-test-cases`),
  create: (projectId: number, data: ApiTestCaseCreateInput) =>
    api.post<ApiTestCase>(`/api/projects/${projectId}/api-test-cases`, data),
  get: (id: number) => api.get<ApiTestCase>(`/api/api-test-cases/${id}`),
  update: (id: number, data: Partial<ApiTestCaseCreateInput>) =>
    api.patch<ApiTestCase>(`/api/api-test-cases/${id}`, data),
  del: (id: number) => api.del<void>(`/api/api-test-cases/${id}`),
  generate: (projectId: number, description: string, requirementId?: number | null) =>
    api.post<{ status: string; api_test_cases: ApiTestCase[]; warnings: string[] }>(
      '/api/ai/generate-api-test-cases',
      { project_id: projectId, description, requirement_id: requirementId ?? null },
    ),
};
