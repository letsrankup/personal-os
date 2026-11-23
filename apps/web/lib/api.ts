// API client: base URL from env, JWT from localStorage, 401 -> /login.
export const API_URL: string =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const TOKEN_KEY = "pos_token";

export function getToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setToken(token: string | null): void {
  if (typeof window === "undefined") return;
  if (token) localStorage.setItem(TOKEN_KEY, token);
  else localStorage.removeItem(TOKEN_KEY);
}

export async function api<T>(path: string, opts: RequestInit = {}): Promise<T> {
  const token = getToken();
  const res = await fetch(`${API_URL}${path}`, {
    ...opts,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(opts.headers ?? {}),
    },
  });
  if (res.status === 401) {
    setToken(null);
    if (
      typeof window !== "undefined" &&
      !window.location.pathname.startsWith("/login")
    ) {
      window.location.href = "/login";
    }
    throw new Error("Session expired — please sign in again.");
  }
  if (!res.ok) {
    let msg = `Request failed (${res.status})`;
    try {
      const j: unknown = await res.json();
      if (j && typeof j === "object" && "detail" in j) {
        const d = (j as { detail: unknown }).detail;
        msg = typeof d === "string" ? d : JSON.stringify(d);
      }
    } catch {
      /* keep default message */
    }
    throw new Error(msg);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}
