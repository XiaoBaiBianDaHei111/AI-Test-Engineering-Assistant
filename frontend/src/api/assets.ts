// Typed API functions for test-asset endpoints.

import { api } from './client';
import type {
  Project,
  ProjectCreate,
  Requirement,
  RequirementCreate,
  TestCase,
  TestCaseCreate,
  TestCaseReview,
  TestPoint,
  TestPointCreate,
  UncoveredTestPoint,
} from '../types';

export const projectsApi = {
  list: () => api.get<Project[]>('/api/projects'),
  create: (data: ProjectCreate) => api.post<Project>('/api/projects', data),
  get: (id: number) => api.get<Project>(`/api/projects/${id}`),
  update: (id: number, data: Partial<ProjectCreate>) =>
    api.patch<Project>(`/api/projects/${id}`, data),
  remove: (id: number) => api.del<void>(`/api/projects/${id}`),
};

export const requirementsApi = {
  list: (projectId: number) =>
    api.get<Requirement[]>(`/api/projects/${projectId}/requirements`),
  create: (projectId: number, data: RequirementCreate) =>
    api.post<Requirement>(`/api/projects/${projectId}/requirements`, data),
  update: (id: number, data: Partial<RequirementCreate>) =>
    api.patch<Requirement>(`/api/requirements/${id}`, data),
  remove: (id: number) => api.del<void>(`/api/requirements/${id}`),
};

export const testCasesApi = {
  list: (projectId: number) => api.get<TestCase[]>(`/api/projects/${projectId}/test-cases`),
  create: (projectId: number, data: TestCaseCreate) =>
    api.post<TestCase>(`/api/projects/${projectId}/test-cases`, data),
  get: (id: number) => api.get<TestCase>(`/api/test-cases/${id}`),
  update: (id: number, data: Partial<TestCaseCreate>) =>
    api.patch<TestCase>(`/api/test-cases/${id}`, data),
  remove: (id: number) => api.del<void>(`/api/test-cases/${id}`),
};

export const testPointsApi = {
  list: (requirementId: number) =>
    api.get<TestPoint[]>(`/api/requirements/${requirementId}/test-points`),
  create: (requirementId: number, data: TestPointCreate) =>
    api.post<TestPoint>(`/api/requirements/${requirementId}/test-points`, data),
  update: (id: number, data: Partial<TestPointCreate>) =>
    api.patch<TestPoint>(`/api/test-points/${id}`, data),
  remove: (id: number) => api.del<void>(`/api/test-points/${id}`),
};

export const testCaseReviewsApi = {
  submit: (id: number) => api.post<TestCase>(`/api/test-cases/${id}/submit-review`),
  review: (id: number, data: { verdict: string; issues?: string[]; suggestions?: string[] }) =>
    api.post<TestCase>(`/api/test-cases/${id}/review`, data),
  resubmit: (id: number) => api.post<TestCase>(`/api/test-cases/${id}/resubmit-review`),
  list: (id: number) => api.get<TestCaseReview[]>(`/api/test-cases/${id}/reviews`),
  uncovered: (projectId: number) =>
    api.get<UncoveredTestPoint[]>(`/api/projects/${projectId}/coverage/uncovered-test-points`),
  executable: (projectId: number) =>
    api.get<TestCase[]>(`/api/projects/${projectId}/test-cases/executable`),
};
