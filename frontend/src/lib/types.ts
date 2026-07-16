export type RiskLevel = "low" | "medium" | "high" | "critical";
export type StrictnessMode = "low" | "medium" | "high" | "custom";
export type ReviewStatus = "pending" | "valid" | "false_positive" | "dismissed" | "needs_review";
export type SessionStatus = "in_progress" | "completed" | "flagged" | "review";

export interface SystemHealth {
  primary_camera: { active: boolean; resolution?: string; fps?: number };
  secondary_camera: { active: boolean; resolution?: string; fps?: number };
  microphone: { active: boolean };
  browser_guard: { active: boolean };
  backend: { connected: boolean };
  database: { connected: boolean; offline_fallback?: boolean };
  network: { stable: boolean; latency_ms?: number };
}

export interface ProctorStatus {
  engine_running: boolean;
  active_session_id?: string | null;
  video_access_token?: string | null;
  last_detection_at?: string;
  last_error?: string;
  primary_camera?: { active: boolean; resolution?: string; fps?: number; frozen?: boolean };
  secondary_camera?: { active: boolean; resolution?: string; fps?: number };
  microphone?: { active: boolean; level?: number };
  video_stream?: { active: boolean; url?: string };
  phone_detection?: { available: boolean; status: string; reason?: string };
  browser_guard?: { active: boolean };
  backend?: { connected: boolean };
  database?: { connected: boolean; offline_fallback?: boolean };
}

export interface Student {
  id: string;
  name: string;
  email: string;
  avatar_url?: string;
}

export interface Exam {
  id: string;
  exam_code?: string;
  title: string;
  duration_minutes: number;
  description?: string;
  semester?: string;
  subject?: string;
  department?: string;
  total_marks?: number;
  status?: "draft" | "scheduled" | "published" | "closed" | "archived" | string;
  start_time?: string | null;
  end_time?: string | null;
  rules?: Record<string, unknown>;
  assignment_id?: string;
  assignment_status?: string;
  assignment_count?: number;
}

export interface QuestionOption {
  option_id: string;
  question_id?: string;
  option_text: string;
  is_correct?: boolean;
  sort_order: number;
}

export interface ExamQuestion {
  question_id: string;
  exam_id: string;
  question_text: string;
  question_type: "mcq" | string;
  marks: number;
  sort_order: number;
  status: string;
  options: QuestionOption[];
}

export interface ExamAttemptResponse {
  response_id: string;
  attempt_id: string;
  question_id: string;
  selected_option_id?: string | null;
  response_text?: string | null;
  is_correct?: boolean | null;
  awarded_marks: number;
  answered_at?: string;
  updated_at?: string | null;
}

export interface ExamAttempt {
  attempt_id: string;
  exam_id: string;
  assignment_id?: string | null;
  session_id?: string | null;
  user_id: string;
  roll_number: string;
  status: "in_progress" | "submitted" | string;
  started_at?: string | null;
  submitted_at?: string | null;
  score: number;
  max_score: number;
  risk_score?: number;
  exam: Pick<Exam, "id" | "title" | "duration_minutes" | "total_marks"> & { exam_code?: string };
  student?: Student;
  questions: ExamQuestion[];
  responses: ExamAttemptResponse[];
}

export interface ExamAttendanceRow {
  assignment_id: string;
  exam_id: string;
  student_user_id: string;
  student_email: string;
  student_name: string;
  assignment_status: string;
  attempt_id?: string | null;
  session_id?: string | null;
  roll_number?: string | null;
  attempt_status: "not_started" | "in_progress" | "submitted" | string;
  started_at?: string | null;
  submitted_at?: string | null;
  score?: number | null;
  max_score?: number | null;
  risk_score: number;
}

export interface ExamAssignment {
  assignment_id: string;
  tenant_id?: string;
  exam_id: string;
  student_user_id: string;
  student_email: string;
  student_name: string;
  student_active: boolean;
  assigned_at?: string | null;
  status: "assigned" | "revoked" | string;
}

export interface Tenant {
  tenant_id: string;
  name: string;
  slug: string;
  status: "active" | "suspended" | "archived" | string;
  plan_name: string;
  settings?: Record<string, unknown>;
  created_at?: string;
  updated_at?: string | null;
}

export interface AdminUser {
  user_id: string;
  tenant_id?: string;
  tenant_name?: string;
  email: string;
  full_name: string;
  role: "student" | "instructor" | "admin";
  is_active: boolean;
  created_at?: string;
  updated_at?: string | null;
}

export interface AuditLog {
  audit_id: string;
  tenant_id?: string;
  actor_user_id?: string;
  actor_email?: string;
  actor_role?: string;
  action: string;
  resource_type?: string;
  resource_id?: string;
  ip_address?: string;
  user_agent?: string;
  details?: Record<string, unknown>;
  created_at: string;
}

export interface RiskContributor {
  id: string;
  label: string;
  delta: number;
  category: "phone" | "face" | "gaze" | "audio" | "browser" | "pattern" | "id" | "room" | "other";
}

export interface RiskScore {
  session_id: string;
  score: number; // 0-100
  level: RiskLevel;
  trend: { t: string; score: number }[];
  contributors: RiskContributor[];
  updated_at: string;
}

export type EventCategory =
  | "phone_detected"
  | "face_missing"
  | "multiple_faces"
  | "gaze_away"
  | "audio_voice"
  | "tab_switch"
  | "url_visit"
  | "fullscreen_exit"
  | "system"
  | "browser_guard";

export interface SessionEvent {
  id: string;
  session_id: string;
  category: EventCategory;
  message: string;
  severity: RiskLevel;
  risk_impact: number;
  timestamp: string;
  camera_source?: "primary" | "secondary";
  evidence_id?: string;
}

export interface EvidenceItem {
  id: string;
  session_id: string;
  event_id?: string;
  type: "screenshot" | "camera_frame" | "audio_clip" | "face" | "id_card" | "room_scan";
  thumbnail_url: string;
  full_url?: string;
  timestamp: string;
  camera_source?: "primary" | "secondary";
  risk_impact?: number;
  label?: string;
}

export interface BrowserActivity {
  id: string;
  session_id: string;
  timestamp: string;
  action: "tab_switch" | "url_open" | "fullscreen_exit" | "copy" | "paste" | "focus_lost";
  url?: string;
  page_title?: string;
  domain?: string;
  domain_category?: "ai_assistant" | "search" | "social" | "education" | "neutral" | "suspicious";
  time_away_ms?: number;
  risk_impact: number;
}

export interface AudioEvent {
  id: string;
  session_id: string;
  timestamp: string;
  type: "voice" | "multiple_voices" | "background_noise" | "silence_break";
  confidence: number;
  duration_ms: number;
  risk_impact: number;
}

export interface Session {
  id: string;
  student: Student;
  exam: Exam;
  status: SessionStatus;
  strictness: StrictnessMode;
  started_at: string;
  ended_at?: string;
  duration_seconds: number;
  risk_score: number;
  risk_level: RiskLevel;
  browser_guard_active: boolean;
  evidence_count: number;
  events_count: number;
  review_status: ReviewStatus;
  health?: SystemHealth;
}

export interface SessionDetail extends Session {
  events: SessionEvent[];
  evidence: EvidenceItem[];
  browser_activity: BrowserActivity[];
  audio_events: AudioEvent[];
  risk: RiskScore;
  notes?: string;
  id_verification?: { verified: boolean; evidence_id?: string };
  room_scan?: { completed: boolean; evidence_ids: string[] };
}

export interface Report {
  id: string;
  session_id: string;
  generated_at: string;
  verdict: RiskLevel;
  summary: string;
  pdf_url?: string;
  bundle_url?: string;
}

export interface AssistantMessage {
  id: string;
  role: "user" | "assistant" | "system";
  content: string;
  timestamp: string;
  quick_actions?: string[];
  confidence?: number;
  intent?: string;
  references?: string[];
}

export interface AssistantQueryRequest {
  query: string;
  mode: "student" | "instructor" | "admin";
  session_id?: string;
}

export interface AssistantQueryResponse {
  reply: string;
  quick_actions?: string[];
  references?: string[];
  confidence?: number;
  intent?: string;
}

export interface ReviewSubmission {
  decision: Exclude<ReviewStatus, "pending">;
  notes?: string;
}

export interface ChecklistItemState {
  id: string;
  label: string;
  description: string;
  status: "passed" | "warning" | "failed" | "optional";
  fix_action?: string;
  critical?: boolean;
}

export interface StrictnessConfig {
  mode: StrictnessMode;
  browser_guard_required: boolean;
  secondary_camera_required: boolean;
  fullscreen_required: boolean;
  copy_paste_allowed: boolean;
  search_engines_allowed: boolean;
  ai_websites_blocked: boolean;
  phone_sensitivity: number;
  gaze_sensitivity: number;
  audio_sensitivity: number;
  risk_threshold_medium: number;
  risk_threshold_high: number;
  risk_threshold_critical: number;
}
