// Typed API functions for AI workflow endpoints.

import { api } from './client';
import type {
  AIAuditLog,
  AnalyzeRequirementResponse,
  ExtractTestPointsResponse,
  GenerateTestCasesResponse,
  GenerationRun,
  ReviewTestCasesResponse,
} from '../types';

export const aiApi = {
  analyzeRequirement: (projectId: number, prdText: string) =>
    api.post<AnalyzeRequirementResponse>('/api/ai/analyze-requirement', {
      project_id: projectId,
      prd_text: prdText,
    }),
  extractTestPoints: (requirementId: number) =>
    api.post<ExtractTestPointsResponse>('/api/ai/extract-test-points', {
      requirement_id: requirementId,
    }),
  generateTestCases: (projectId: number, testPointIds: number[]) =>
    api.post<GenerateTestCasesResponse>('/api/ai/generate-test-cases', {
      project_id: projectId,
      test_point_ids: testPointIds,
    }),
  getGenerationRun: (runId: number) =>
    api.get<GenerationRun>(`/api/ai/generation-runs/${runId}`),
  listGenerationRuns: (projectId: number) =>
    api.get<GenerationRun[]>(`/api/ai/generation-runs?project_id=${projectId}`),
  reviewTestCases: (testCaseIds: number[]) =>
    api.post<ReviewTestCasesResponse>('/api/ai/review-test-cases', {
      test_case_ids: testCaseIds,
    }),
  listAudit: (params?: { agent?: string; status?: string; limit?: number }) =>
    api.get<AIAuditLog[]>(
      `/api/ai/audit${buildQuery(params)}`,
    ),
};

function buildQuery(params?: Record<string, string | number | undefined>): string {
  if (!params) return '';
  const search = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined) search.set(key, String(value));
  }
  const qs = search.toString();
  return qs ? `?${qs}` : '';
}
