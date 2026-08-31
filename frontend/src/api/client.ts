// Minimal fetch wrapper with a consistent error type.

export interface ApiErrorBody {
  code: string;
  message: string;
  detail?: unknown;
}

export class ApiError extends Error {
  status: number;
  code: string;
  detail?: unknown;

  constructor(status: number, body: ApiErrorBody) {
    super(body.message);
    this.name = 'ApiError';
    this.status = status;
    this.code = body.code;
    this.detail = body.detail;
  }
}

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const response = await fetch(path, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });

  if (response.status === 204) {
    return undefined as T;
  }

  let body: unknown = null;
  try {
    body = await response.json();
  } catch {
    // non-JSON body
  }

  if (!response.ok) {
    const errorBody: ApiErrorBody =
      (body as ApiErrorBody) ?? { code: 'HTTP_ERROR', message: `HTTP ${response.status}` };
    throw new ApiError(response.status, errorBody);
  }
  return body as T;
}

export const api = {
  get: <T>(path: string) => request<T>(path),
  post: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: 'POST', body: data !== undefined ? JSON.stringify(data) : undefined }),
  patch: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: 'PATCH', body: data !== undefined ? JSON.stringify(data) : undefined }),
  del: <T>(path: string) => request<T>(path, { method: 'DELETE' }),
  put: <T>(path: string, data?: unknown) =>
    request<T>(path, { method: 'PUT', body: data !== undefined ? JSON.stringify(data) : undefined }),
  getText: async (path: string): Promise<string> => {
    const response = await fetch(path);
    if (!response.ok) {
      throw new ApiError(response.status, { code: 'HTTP_ERROR', message: `HTTP ${response.status}` });
    }
    return response.text();
  },
  putText: async (path: string, text: string): Promise<void> => {
    const response = await fetch(path, {
      method: 'PUT',
      headers: { 'Content-Type': 'text/plain' },
      body: text,
    });
    if (!response.ok) {
      throw new ApiError(response.status, { code: 'HTTP_ERROR', message: `HTTP ${response.status}` });
    }
  },
};

export function errorMessage(error: unknown): string {
  if (error instanceof ApiError) return error.message;
  if (error instanceof Error) return error.message;
  return String(error);
}
