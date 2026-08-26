export interface User {
  id: number;
  username: string;
  display_name: string;
  is_admin: boolean;
}

export interface Asset {
  id: number;
  kind: string;
  filename: string;
  url: string;
  width: number | null;
  height: number | null;
  created_at: string;
}

export interface Template {
  id: number;
  name: string;
  category: string;
  positive_prompt: string;
  negative_prompt: string;
  params: Record<string, any>;
  is_builtin: boolean;
  created_at: string;
}

export interface Project {
  id: number;
  name: string;
  customer: string;
  description: string;
  task_count: number;
  created_at: string;
}

export interface Task {
  id: number;
  mode: "t2i" | "img2img" | "inpaint";
  status: "pending" | "queued" | "running" | "done" | "error";
  progress: number;
  step: number;
  total_steps: number;
  project_id: number | null;
  template_id: number | null;
  prompt: string;
  negative_prompt: string;
  params: Record<string, any>;
  error: string | null;
  created_at: string;
  finished_at: string | null;
  outputs: Asset[];
  input_asset: Asset | null;
}
