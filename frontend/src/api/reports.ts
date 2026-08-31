// Typed API functions for test reports + quality summaries (Phase 8).

import { api } from './client';
import type { QualitySummary, ReportListItem, TestReport } from '../types';

export const reportsApi = {
  list: (projectId: number) => api.get<ReportListItem[]>(`/api/reports?project_id=${projectId}`),
  get: (runId: number) => api.get<TestReport>(`/api/reports/${runId}`),
  generate: (runId: number) => api.post<TestReport>(`/api/reports/${runId}/generate`),
  htmlUrl: (runId: number) => `/api/reports/${runId}/html`,
  exportUrl: (runId: number, format: 'json' | 'markdown') =>
    `/api/reports/${runId}/export?format=${format}`,
  generateQualitySummary: (reportId: number) =>
    api.post<QualitySummary>(`/api/quality-summary/${reportId}`),
};
