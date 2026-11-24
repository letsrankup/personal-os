export interface User { id: string; email: string; name: string; role: string; is_active: boolean }
export interface TokenOut { access_token: string; token_type: string }

export interface Overview {
  total_tasks: number;
  tasks_by_status: Record<string, number>;
  completed_tasks: number;
  running_tasks: number;
  failed_tasks: number;
  active_agents: number;
  projects_in_progress: number;
  recent_activity: { action: string; actor: string; entity: string | null; created_at: string }[];
  latest_reports: { id: string; kind: string; title: string; created_at: string }[];
}

export interface Conversation { id: string; title: string; summary: string; created_at: string; updated_at: string }
export interface Message { id: string; role: string; agent_key: string | null; content: string; meta: Record<string, unknown>; created_at: string }
export interface CommandOut { task_id: string; status: string; reply: string; agent: string; conversation_id: string; approval_id: string | null }
export interface Approval { id: string; task_id: string | null; action: string; summary: string; payload: Record<string, unknown>; status: string; created_at: string; decided_at: string | null }

export interface Agent { id: string; key: string; name: string; role: string; status: string; model: string | null }

export interface TaskStep { id: string; order: number; agent_key: string; description: string; status: string; error: string | null; started_at: string | null; completed_at: string | null }
export interface Task {
  id: string; title: string; description: string; agent_key: string; priority: string;
  status: string; permission_tier: string; result: string | null; error: string | null;
  verified: boolean; logs: { ts?: string; level?: string; message?: string }[];
  started_at: string | null; completed_at: string | null; created_at: string;
}
export interface TaskDetail extends Task { steps: TaskStep[] }

export interface Project { id: string; name: string; description: string; status: string; meta: Record<string, unknown>; total_tasks: number; completed_tasks: number; progress_pct: number; created_at: string; updated_at: string }
export interface Client { id: string; name: string; email: string | null; phone: string | null; company: string | null; category: string; status: string; notes: string; meta: Record<string, unknown>; created_at: string; updated_at: string }
export interface FileRecord { id: string; project_id: string | null; name: string; path: string; kind: string; size_bytes: number | null; meta: Record<string, unknown>; created_at: string; updated_at: string }
export interface Report { id: string; kind: string; title: string; content: string; data: Record<string, unknown>; period_start: string | null; period_end: string | null; created_at: string; updated_at: string }
export interface Memory { id: string; kind: string; title: string; content: string; tags: string[]; source_ref: string | null; created_at: string; updated_at: string }
export interface Integration { id: string; provider: string; status: string; account_label: string | null; config: Record<string, unknown>; last_checked_at: string | null; created_at: string; updated_at: string }
export interface ScheduledJob { id: string; name: string; kind: string; report_kind: string; interval: string; enabled: boolean; last_run_at: string | null; next_run_at: string | null; created_at: string; updated_at: string }
export interface JobRunResult extends ScheduledJob { executed?: boolean; report_id?: string | null; error?: string | null }
export interface Permission { id: string; action: string; tier: string; description: string }
export interface Activity { id: string; actor: string; action: string; entity: string | null; entity_id: string | null; details: Record<string, unknown>; created_at: string }
export interface FinanceEntry { id: string; kind: string; amount: number; currency: string; category: string; note: string; occurred_at: string; created_at: string }
export interface Health { status: string; service: string; db: string; ai_provider?: string }
