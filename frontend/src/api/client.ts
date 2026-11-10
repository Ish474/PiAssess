// Small fetch wrapper: attaches credentials + CSRF header, normalises errors.
export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

const CSRF_KEY = "piassess_csrf";
const USER_KEY = "piassess_user";

export function setAuth(csrf: string, user: unknown) {
  localStorage.setItem(CSRF_KEY, csrf);
  localStorage.setItem(USER_KEY, JSON.stringify(user));
}
export function clearAuth() {
  localStorage.removeItem(CSRF_KEY);
  localStorage.removeItem(USER_KEY);
}
export function getCsrf(): string {
  return localStorage.getItem(CSRF_KEY) || "";
}
export function getCachedUser<T>(): T | null {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as T;
  } catch {
    return null;
  }
}

async function request<T>(method: string, path: string, body?: unknown, isForm = false): Promise<T> {
  const headers: Record<string, string> = {};
  if (!isForm && body !== undefined) headers["Content-Type"] = "application/json";
  const csrf = getCsrf();
  if (csrf) headers["X-CSRF-Token"] = csrf;

  const res = await fetch(path, {
    method,
    headers,
    credentials: "include",
    body: isForm ? (body as FormData) : body !== undefined ? JSON.stringify(body) : undefined,
  });

  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    clearAuth();
    window.location.href = "/login";
    throw new ApiError(401, "Please sign in again.");
  }

  if (!res.ok) {
    let detail = `Request failed (${res.status}).`;
    try {
      const data = await res.json();
      if (typeof data.detail === "string") detail = data.detail;
      else if (Array.isArray(data.detail)) {
        const first = data.detail[0];
        detail = first?.msg ? `Please check the form: ${first.msg}` : detail;
      }
    } catch { /* keep default */ }
    throw new ApiError(res.status, detail);
  }

  const ct = res.headers.get("content-type") || "";
  if (ct.includes("application/json")) return (await res.json()) as T;
  return (await res.blob()) as unknown as T;
}

export const api = {
  get: <T>(path: string) => request<T>("GET", path),
  post: <T>(path: string, body?: unknown) => request<T>("POST", path, body),
  postForm: <T>(path: string, form: FormData) => request<T>("POST", path, form, true),
  put: <T>(path: string, body?: unknown) => request<T>("PUT", path, body),
  patch: <T>(path: string, body?: unknown) => request<T>("PATCH", path, body),
  delete: <T>(path: string) => request<T>("DELETE", path),
};

export function downloadFile(path: string, filename: string) {
  request<Blob>("GET", path)
    .then((blob) => {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      a.click();
      URL.revokeObjectURL(url);
    })
    .catch((e) => alert(e instanceof Error ? e.message : "Download failed."));
}
