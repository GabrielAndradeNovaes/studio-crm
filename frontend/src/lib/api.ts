import type { AuthSessionResponse } from "./types";

const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL?.replace(/\/$/, "") ||
  "http://localhost:8000/api/v1";

/**
 * Access Token mantido estritamente em memória JS (nunca em localStorage/sessionStorage),
 * protegendo contra exfiltração por XSS. O Refresh Token trafega apenas em cookie HttpOnly.
 */
let inMemoryAccessToken: string | null = null;
let refreshPromise: Promise<AuthSessionResponse | null> | null = null;

export function setAccessToken(token: string | null): void {
  inMemoryAccessToken = token;
}

export function getAccessToken(): string | null {
  return inMemoryAccessToken;
}

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly detail: string;

  constructor(status: number, code: string, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.detail = detail;
  }
}

async function parseError(res: Response): Promise<ApiError> {
  try {
    const data = await res.json();
    if (typeof data?.detail === "string") {
      return new ApiError(res.status, data.code || "API_ERROR", data.detail);
    }
    if (Array.isArray(data?.detail) && data.detail.length > 0) {
      const firstMsg = data.detail[0]?.msg || "Dados inválidos.";
      return new ApiError(res.status, "VALIDATION_ERROR", firstMsg);
    }
  } catch {
    // ignore JSON parse failure
  }
  return new ApiError(res.status, "HTTP_ERROR", `Erro de comunicação (${res.status}).`);
}

export async function silentRefreshSession(): Promise<AuthSessionResponse | null> {
  if (refreshPromise) {
    return refreshPromise;
  }
  refreshPromise = (async () => {
    try {
      const res = await fetch(`${API_BASE_URL}/auth/refresh`, {
        method: "POST",
        credentials: "include",
        headers: { Accept: "application/json" },
      });
      if (!res.ok) {
        inMemoryAccessToken = null;
        return null;
      }
      const data = (await res.json()) as AuthSessionResponse;
      if (data.access_token) {
        inMemoryAccessToken = data.access_token;
      }
      return data;
    } catch {
      inMemoryAccessToken = null;
      return null;
    } finally {
      refreshPromise = null;
    }
  })();

  return refreshPromise;
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { skipAuthRefresh?: boolean } = {}
): Promise<T> {
  const { skipAuthRefresh = false, headers, ...rest } = options;
  const reqHeaders = new Headers(headers);
  reqHeaders.set("Accept", "application/json");
  if (rest.body && !reqHeaders.has("Content-Type")) {
    reqHeaders.set("Content-Type", "application/json");
  }
  if (inMemoryAccessToken && !reqHeaders.has("Authorization")) {
    reqHeaders.set("Authorization", `Bearer ${inMemoryAccessToken}`);
  }

  let res = await fetch(`${API_BASE_URL}${path}`, {
    ...rest,
    headers: reqHeaders,
    credentials: "include",
  });

  if (res.status === 401 && !skipAuthRefresh && !path.startsWith("/auth/")) {
    const refreshed = await silentRefreshSession();
    if (refreshed?.access_token) {
      reqHeaders.set("Authorization", `Bearer ${refreshed.access_token}`);
      res = await fetch(`${API_BASE_URL}${path}`, {
        ...rest,
        headers: reqHeaders,
        credentials: "include",
      });
    }
  }

  if (!res.ok) {
    throw await parseError(res);
  }

  if (res.status === 204) {
    return undefined as T;
  }
  return (await res.json()) as T;
}
