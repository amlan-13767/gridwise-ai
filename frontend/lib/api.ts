export const API = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
const KEY = "gridwise_token";
const USER = "gridwise_user";

export type User = { id: number; name: string; email: string; role: Role; assigned_zone_id: number | null };
export type Role = "super_admin" | "energy_manager" | "zone_manager" | "viewer";

export const getToken = () => (typeof window === "undefined" ? null : localStorage.getItem(KEY));
export const getUser = (): User | null => {
  if (typeof window === "undefined") return null;
  try { return JSON.parse(localStorage.getItem(USER) || "null"); } catch { return null; }
};
export const setSession = (t: string, u: User) => { localStorage.setItem(KEY, t); localStorage.setItem(USER, JSON.stringify(u)); };
export const clearSession = () => { localStorage.removeItem(KEY); localStorage.removeItem(USER); };

export class ApiError extends Error { status: number; constructor(m: string, s: number) { super(m); this.status = s; } }

export async function api<T = any>(path: string, opts: { method?: string; body?: unknown } = {}): Promise<T> {
  const t = getToken();
  const res = await fetch(API + path, {
    method: opts.method || "GET",
    headers: { "Content-Type": "application/json", ...(t ? { Authorization: `Bearer ${t}` } : {}) },
    body: opts.body !== undefined ? JSON.stringify(opts.body) : undefined,
  });
  if (res.status === 401 && t && !path.includes("/auth/login")) {
    clearSession(); if (typeof window !== "undefined") window.location.href = "/login";
  }
  if (!res.ok) {
    let msg = res.statusText;
    try { const j = await res.json(); msg = typeof j.detail === "string" ? j.detail : j.detail ? JSON.stringify(j.detail) : j.reason || msg; } catch {}
    throw new ApiError(msg, res.status);
  }
  return res.json();
}

export async function downloadCsv(path: string, filename: string) {
  const res = await fetch(API + path, { headers: { Authorization: `Bearer ${getToken()}` } });
  if (!res.ok) throw new ApiError("Export failed", res.status);
  const blob = await res.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob); a.download = filename; document.body.appendChild(a); a.click(); a.remove();
  return blob.size;
}

export const qs = (o: Record<string, string | number | undefined | null>) => {
  const p = Object.entries(o).filter(([, v]) => v !== undefined && v !== null && v !== "" && v !== "all");
  return p.length ? "?" + p.map(([k, v]) => `${k}=${encodeURIComponent(String(v))}`).join("&") : "";
};

export const canManage = (u: User | null) => !!u && (u.role === "super_admin" || u.role === "energy_manager");
export const isAdmin = (u: User | null) => u?.role === "super_admin";
