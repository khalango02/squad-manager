const BASE = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit, isRetry = false): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    ...init,
    credentials: "include", // sends httpOnly cookies automatically
    headers: {
      "Content-Type": "application/json",
      ...init?.headers,
    },
  });

  // Auto-refresh on 401: try once to rotate the refresh token, then retry
  if (res.status === 401 && !isRetry && path !== "/auth/login" && path !== "/auth/refresh") {
    const refreshed = await fetch(`${BASE}/auth/refresh`, {
      method: "POST",
      credentials: "include",
    });
    if (refreshed.ok) {
      return request(path, init, true);
    }
    if (typeof window !== "undefined") {
      window.location.href = "/login";
    }
    throw new Error("Session expired");
  }

  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail ?? "Request failed");
  }
  if (res.status === 204) return undefined as T;
  return res.json();
}

export type User = {
  id: string;
  email: string;
  is_active: boolean;
  created_at: string;
};

export type Agent = {
  id: string;
  owner_id: string;
  name: string;
  description: string | null;
  md_content: string;
  created_at: string;
  updated_at: string;
};

export type Connection = {
  id: string;
  source_id: string;
  target_id: string;
  label: string;
  created_at: string;
};

export const api = {
  auth: {
    login: (email: string, password: string) =>
      request<User>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    register: (email: string, password: string) =>
      request<User>("/auth/register", {
        method: "POST",
        body: JSON.stringify({ email, password }),
      }),
    logout: () => request<void>("/auth/logout", { method: "POST" }),
    me: () => request<User>("/auth/me"),
  },
  agents: {
    list: () => request<Agent[]>("/agents/"),
    get: (id: string) => request<Agent>(`/agents/${id}`),
    create: (data: { name: string; description?: string; md_content?: string }) =>
      request<Agent>("/agents/", { method: "POST", body: JSON.stringify(data) }),
    update: (id: string, data: Partial<Pick<Agent, "name" | "description" | "md_content">>) =>
      request<Agent>(`/agents/${id}`, { method: "PATCH", body: JSON.stringify(data) }),
    delete: (id: string) => request<void>(`/agents/${id}`, { method: "DELETE" }),
  },
  connections: {
    list: () => request<Connection[]>("/connections/"),
    create: (data: { source_id: string; target_id: string; label?: string }) =>
      request<Connection>("/connections/", { method: "POST", body: JSON.stringify(data) }),
    delete: (id: string) => request<void>(`/connections/${id}`, { method: "DELETE" }),
  },
};
