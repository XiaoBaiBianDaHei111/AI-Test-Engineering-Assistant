// Typed API functions for execution evidence (Phase 6).

import { api } from './client';
import type { ConsoleEntry, Evidence, NetworkEntry, TraceParse } from '../types';

export const evidenceApi = {
  listCase: (runId: number, runCaseId: number) =>
    api.get<Evidence[]>(`/api/runs/${runId}/cases/${runCaseId}/evidence`),
  listRun: (runId: number) => api.get<Evidence[]>(`/api/runs/${runId}/evidence`),
  contentUrl: (evidenceId: number) => `/api/evidence/${evidenceId}/content`,
  getTraceParse: (evidenceId: number) =>
    api.get<TraceParse>(`/api/evidence/${evidenceId}/trace-parse`),
  getConsole: (evidenceId: number) =>
    api.get<ConsoleEntry[]>(`/api/evidence/${evidenceId}/content`),
  getNetwork: (evidenceId: number) =>
    api.get<NetworkEntry[]>(`/api/evidence/${evidenceId}/content`),
};
