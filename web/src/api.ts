import { create } from "zustand";
import type { Asset, Project, QueueOverview, Task, Template, User } from "./types";

const BASE = import.meta.env.DEV ? "http://127.0.0.1:8000" : "";

const TOKEN_KEY = "rvx_token";
const USER_KEY = "rvx_user";

function loadPersisted(): { token: string; user: User | null } {
  try {
    const token = localStorage.getItem(TOKEN_KEY) || "";
    const raw = localStorage.getItem(USER_KEY);
    return { token, user: raw ? (JSON.parse(raw) as User) : null };
  } catch {
    // 内嵌 webview 可能禁用 localStorage，仅用内存态
    return { token: "", user: null };
  }
}

interface AuthState {
  token: string;
  user: User | null;
  login: (token: string, user: User) => void;
  logout: () => void;
}

export const useAuth = create<AuthState>((set) => ({
  ...loadPersisted(),
  login: (token, user) => {
    set({ token, user });
    try {
      localStorage.setItem(TOKEN_KEY, token);
      localStorage.setItem(USER_KEY, JSON.stringify(user));
    } catch {
      /* ignore */
    }
  },
  logout: () => {
    set({ token: "", user: null });
    try {
      localStorage.removeItem(TOKEN_KEY);
      localStorage.removeItem(USER_KEY);
    } catch {
      /* ignore */
    }
  },
}));

/** 命令式场景（fetch 头、URL 拼接）取当前 token */
function currentToken(): string {
  return useAuth.getState().token;
}

async function request<T>(method: string, path: string, body?: any): Promise<T> {
  const headers: Record<string, string> = {};
  const token = currentToken();
  if (token) headers["X-Auth-Token"] = token;
  let payload: BodyInit | undefined;
  if (body instanceof FormData) {
    payload = body;
  } else if (body !== undefined) {
    headers["Content-Type"] = "application/json";
    payload = JSON.stringify(body);
  }
  const resp = await fetch(`${BASE}${path}`, { method, headers, body: payload });
  if (resp.status === 401) {
    useAuth.getState().logout();
    window.location.hash = "#/login";
    throw new Error("登录已过期");
  }
  if (!resp.ok) {
    let msg = `${resp.status}`;
    try {
      const data = await resp.json();
      msg = data.detail || JSON.stringify(data);
    } catch {
      /* ignore */
    }
    throw new Error(msg);
  }
  return resp.json() as Promise<T>;
}

export const api = {
  login: (username: string, password: string) =>
    request<{ token: string; user: User }>("POST", "/api/auth/login", { username, password }),
  templates: () => request<Template[]>("GET", "/api/templates"),
  saveTemplate: (t: Partial<Template>, id?: number) =>
    id ? request<Template>("PUT", `/api/templates/${id}`, t) : request<Template>("POST", "/api/templates", t),
  deleteTemplate: (id: number) => request<any>("DELETE", `/api/templates/${id}`),
  projects: () => request<Project[]>("GET", "/api/projects"),
  saveProject: (p: Partial<Project>, id?: number) =>
    id ? request<Project>("PUT", `/api/projects/${id}`, p) : request<Project>("POST", "/api/projects", p),
  deleteProject: (id: number) => request<any>("DELETE", `/api/projects/${id}`),
  tasks: (params?: Record<string, any>) => {
    const qs = params ? "?" + new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString() : "";
    return request<Task[]>("GET", `/api/tasks${qs}`);
  },
  createTask: (body: any) => request<Task>("POST", "/api/tasks", body),
  taskDetail: (id: number) => request<Task>("GET", `/api/tasks/${id}`),
  cancelTask: (id: number) => request<Task>("POST", `/api/tasks/${id}/cancel`),
  queueOverview: () => request<QueueOverview>("GET", "/api/tasks/meta/queue"),
  users: () => request<User[]>("GET", "/api/auth/users"),
  createUser: (body: { username: string; password: string; display_name?: string; is_admin?: boolean }) =>
    request<User>("POST", "/api/auth/users", body),
  updateUser: (id: number, body: { password?: string; display_name?: string; is_admin?: boolean }) =>
    request<User>("PUT", `/api/auth/users/${id}`, body),
  deleteUser: (id: number) => request<any>("DELETE", `/api/auth/users/${id}`),
  upload: (blob: Blob, filename: string) => {
    const fd = new FormData();
    fd.append("file", blob, filename);
    return request<Asset>("POST", "/api/assets/upload", fd);
  },
  translate: (text: string) =>
    request<{ english: string; source: string; unknown: string[]; violations: string[] }>(
      "POST", "/api/prompt/translate", { text }),
  presets: () =>
    request<{ category: string; items: { name: string; prompt_en: string }[] }[]>(
      "GET", "/api/prompt/presets"),
  cadConvert: (file: File, fields: Record<string, string>) => {
    const fd = new FormData();
    fd.append("file", file);
    for (const [k, v] of Object.entries(fields)) fd.append(k, v);
    return request<{ assets: Asset[]; layers: Record<string, number>; entities: number }>(
      "POST", "/api/cad/convert", fd);
  },
  floorplanAnalyze: (file: File) => {
    const fd = new FormData();
    fd.append("file", file);
    return request<{
      asset: Asset;
      rooms: { label: string; room_type: string; bbox: number[] | null; source: string }[];
      size: [number, number];
      texts: string[];
      room_types: Record<string, string>;
    }>("POST", "/api/floorplan/analyze", fd);
  },
  floorplanRender: (body: any) =>
    request<{ tasks: any[] }>("POST", "/api/floorplan/render", body),
  floorplanMatrix: (body: any) =>
    request<{ tasks: any[] }>("POST", "/api/floorplan/matrix", body),
  renovateCompare: (taskId: number, outputIndex = 0) =>
    request<Asset>("POST", "/api/renovate/compare", { task_id: taskId, output_index: outputIndex }),
  estimate: (body: any) =>
    request<{
      mm_per_px: number; scale_auto: boolean; total_area_sqm: number; note: string;
      items: { label: string; width_m: number; depth_m: number; area_sqm: number; wall_len_m: number }[];
    }>("POST", "/api/estimate", body),
  pdfProposal: (body: {
    title: string; customer: string; project_id?: number; task_ids: number[];
    notes?: { heading: string; paragraphs: string[] }[];
    moodboard_asset_ids?: number[];
    material_asset_id?: number | null;
  }) => request<Asset>("POST", "/api/pdf/proposal", body),
  pdfEstimate: (body: any) => request<Asset>("POST", "/api/pdf/estimate", body),
  pdfCompare: (body: any) => request<Asset>("POST", "/api/pdf/compare", body),
  health: () => request<{ mode: string; healthy: boolean }>("GET", "/api/tasks/meta/health"),
};

/** 带 token 的资源地址（img src / EventSource 用） */
export function assetUrl(path: string): string {
  const sep = path.includes("?") ? "&" : "?";
  return `${BASE}${path}${sep}token=${encodeURIComponent(currentToken())}`;
}

export function sseUrl(taskId: number): string {
  return `${BASE}/api/tasks/${taskId}/events?token=${encodeURIComponent(currentToken())}`;
}
