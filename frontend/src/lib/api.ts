/* eslint-disable @typescript-eslint/no-explicit-any */
import { API_BASE_URL, VIDEO_BASE_URL, endpoints } from "@/config/endpoints";
import { authHeaders, clearAuthSession, setAuthSession, type AuthSession, type AuthUser } from "./auth";
import type {
  AssistantQueryRequest,
  AssistantQueryResponse,
  AudioEvent,
  AdminUser,
  AuditLog,
  BrowserActivity,
  EvidenceItem,
  Exam,
  ExamAssignment,
  ExamAttendanceRow,
  ExamAttempt,
  ExamQuestion,
  ProctorStatus,
  Report,
  ReviewSubmission,
  RiskScore,
  Session,
  SessionDetail,
  SessionEvent,
  Tenant,
} from "./types";

async function http<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...authHeaders(),
      ...(init?.headers ?? {}),
    },
    ...init,
  });
  const text = await res.text();
  const data = text ? JSON.parse(text) : {};
  if (!res.ok) {
    if (res.status === 401) {
      clearAuthSession();
      if (typeof window !== "undefined" && !window.location.pathname.startsWith("/login")) {
        window.location.assign("/login");
      }
    }
    const message = data?.message || data?.detail || `API ${res.status}: ${res.statusText}`;
    throw new Error(message);
  }
  return data as T;
}

function mapRiskLevel(score: number): "low" | "medium" | "high" | "critical" {
  if (score < 20) return "low";
  if (score < 50) return "medium";
  if (score < 80) return "high";
  return "critical";
}

function mapReviewMark(mark?: string | null): any {
  if (!mark) return "pending";
  const m = mark.toLowerCase();
  if (m.includes("valid")) return "valid";
  if (m.includes("false")) return "false_positive";
  if (m.includes("dismiss")) return "dismissed";
  return "needs_review";
}

function inferEventCategory(eventType: string): import("./types").EventCategory {
  const t = (eventType ?? "").toLowerCase();
  if (t.includes("phone")) return "phone_detected";
  if (t.includes("face") && t.includes("missing")) return "face_missing";
  if (t.includes("multiple") && t.includes("face")) return "multiple_faces";
  if (t.includes("gaze") || t.includes("look away")) return "gaze_away";
  if (t.includes("audio") || t.includes("voice")) return "audio_voice";
  if (t.includes("tab")) return "tab_switch";
  if (t.includes("fullscreen")) return "fullscreen_exit";
  if (t.includes("url") || t.includes("browser") || t.includes("keyboard") || t.includes("clipboard") || t.includes("devtools")) return "url_visit";
  return "system";
}

function mapBackendEventToSessionEvent(raw: any): SessionEvent {
  return {
    id: String(raw.event_id || `evt_${raw.event_time || Math.random()}`),
    session_id: raw.session_id,
    category: inferEventCategory(raw.event_type ?? ""),
    message: raw.notes || raw.event_type || "Unknown event",
    severity: mapRiskLevel(raw.risk_points ?? 0),
    risk_impact: raw.risk_points ?? 0,
    timestamp: raw.event_time || raw.timestamp || new Date().toISOString(),
  };
}

function mapBackendExam(raw: any): Exam {
  return {
    id: raw.exam_id || raw.id || raw.exam_code,
    exam_code: raw.exam_code || "",
    title: raw.title || raw.exam_code || "Untitled exam",
    duration_minutes: Number(raw.duration_minutes || 60),
    description: raw.description || "",
    semester: raw.semester || "",
    subject: raw.subject || "",
    department: raw.department || "",
    total_marks: Number(raw.total_marks || 0),
    status: raw.status || "draft",
    start_time: raw.start_time ?? null,
    end_time: raw.end_time ?? null,
    rules: raw.rules || {},
    assignment_id: raw.assignment_id,
    assignment_status: raw.assignment_status,
    assignment_count: Number(raw.assignment_count || 0),
  };
}

function mapBackendQuestion(raw: any): ExamQuestion {
  return {
    question_id: raw.question_id,
    exam_id: raw.exam_id,
    question_text: raw.question_text || "",
    question_type: raw.question_type || "mcq",
    marks: Number(raw.marks || 1),
    sort_order: Number(raw.sort_order || 0),
    status: raw.status || "active",
    options: (raw.options || []).map((option: any) => ({
      option_id: option.option_id,
      question_id: option.question_id,
      option_text: option.option_text || "",
      is_correct: option.is_correct,
      sort_order: Number(option.sort_order || 0),
    })),
  };
}

function mapBackendAttempt(raw: any): ExamAttempt {
  return {
    attempt_id: raw.attempt_id,
    exam_id: raw.exam_id,
    assignment_id: raw.assignment_id,
    session_id: raw.session_id,
    user_id: raw.user_id,
    roll_number: raw.roll_number || "",
    status: raw.status || "in_progress",
    started_at: raw.started_at,
    submitted_at: raw.submitted_at,
    score: Number(raw.score || 0),
    max_score: Number(raw.max_score || 0),
    risk_score: Number(raw.risk_score || 0),
    exam: {
      id: raw.exam?.id || raw.exam_id,
      exam_code: raw.exam?.exam_code || raw.exam_code || "",
      title: raw.exam?.title || raw.exam_title || "Exam",
      duration_minutes: Number(raw.exam?.duration_minutes || raw.duration_minutes || 60),
      total_marks: Number(raw.exam?.total_marks || raw.total_marks || raw.max_score || 0),
    },
    student: raw.student
      ? {
          id: raw.student.id || raw.user_id,
          name: raw.student.name || "",
          email: raw.student.email || "",
        }
      : undefined,
    questions: (raw.questions || []).map(mapBackendQuestion),
    responses: (raw.responses || []).map((response: any) => ({
      response_id: response.response_id,
      attempt_id: response.attempt_id,
      question_id: response.question_id,
      selected_option_id: response.selected_option_id,
      response_text: response.response_text,
      is_correct: response.is_correct,
      awarded_marks: Number(response.awarded_marks || 0),
      answered_at: response.answered_at,
      updated_at: response.updated_at,
    })),
  };
}

function mapBackendSessionSummaryToSession(raw: any): Session {
  const score = Math.min(Number(raw.final_score ?? raw.risk_score ?? 0), 100);
  return {
    id: raw.session_id,
    student: {
      id: raw.user_id || raw.student_id || "",
      name: raw.student_name || raw.student_id || "Unknown student",
      email: raw.student_email || "",
    },
    exam: {
      id: raw.exam_id || raw.exam_code || "",
      title: raw.exam_title || raw.exam_code || "Exam session",
      duration_minutes: Number(raw.duration_minutes || 0),
    },
    status: raw.status === "Active" ? "in_progress" : "completed",
    strictness: "medium",
    started_at: raw.start_time || new Date().toISOString(),
    ended_at: raw.end_time || undefined,
    duration_seconds: 0,
    risk_score: score,
    risk_level: mapRiskLevel(score),
    browser_guard_active: false,
    evidence_count: Number(raw.evidence_count || 0),
    events_count: Number(raw.event_count || 0),
    review_status: mapReviewMark(raw.review_mark),
  };
}

function resolveBackendUrl(path: string): string {
  if (!path) return "";
  if (path.startsWith("http")) return path;
  let cleanPath = path.replace(/\\/g, "/");
  if (cleanPath.startsWith("screenshots/")) cleanPath = cleanPath.replace("screenshots/", "captures/");
  return `${API_BASE_URL}${cleanPath.startsWith("/") ? cleanPath : `/${cleanPath}`}`;
}

function mapBackendEvidenceToEvidenceItem(raw: any, sessionId?: string): EvidenceItem {
  const url = resolveBackendUrl(raw.filepath || raw.path || raw.image_url || "");
  return {
    id: raw.evidence_id || raw.id || raw.filename || `evd_${Math.random().toString(36).slice(2)}`,
    session_id: raw.session_id ?? sessionId ?? "",
    event_id: raw.event_id,
    type: raw.evidence_type || "screenshot",
    timestamp: raw.timestamp || raw.created_at || new Date().toISOString(),
    risk_impact: raw.risk_points ?? 0,
    camera_source: raw.camera || "primary",
    thumbnail_url: url,
    full_url: url,
    label: raw.label || raw.event_type,
  };
}

function inferAudioType(eventType: string): AudioEvent["type"] {
  const t = (eventType ?? "").toLowerCase();
  if (t.includes("multiple")) return "multiple_voices";
  if (t.includes("silence")) return "silence_break";
  if (t.includes("noise") || t.includes("sound")) return "background_noise";
  return "voice";
}

function mapBackendAudioToAudioEvent(raw: any): AudioEvent {
  return {
    id: String(raw.id || raw.event_id || `aud_${Math.random().toString(36).slice(2)}`),
    session_id: raw.session_id,
    timestamp: raw.timestamp || raw.event_time || new Date().toISOString(),
    type: inferAudioType(raw.event_type),
    confidence: raw.confidence ?? 1,
    duration_ms: raw.duration_ms ?? 1000,
    risk_impact: raw.risk_points ?? raw.risk_impact ?? 0,
  };
}

function mapBackendBrowserActivityToBrowserActivity(raw: any): BrowserActivity {
  const t = (raw.event_type || raw.type || "").toLowerCase();
  let action: BrowserActivity["action"] = "url_open";
  if (t.includes("tab")) action = "tab_switch";
  else if (t.includes("fullscreen")) action = "fullscreen_exit";
  else if (t.includes("copy")) action = "copy";
  else if (t.includes("paste")) action = "paste";
  else if (t.includes("focus") || t.includes("keyboard") || t.includes("devtools")) action = "focus_lost";
  return {
    id: raw.id || `${raw.timestamp || raw.time}-${action}`,
    session_id: raw.session_id,
    timestamp: raw.timestamp || raw.time || new Date().toISOString(),
    action,
    url: raw.url,
    page_title: raw.title,
    domain_category: raw.category ? "suspicious" : undefined,
    risk_impact: raw.risk_impact ?? raw.risk_points ?? 0,
  };
}

export const api = {
  async login(email: string, password: string): Promise<AuthSession> {
    const session = await http<Omit<AuthSession, "logged_in_at">>(endpoints.login, {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
    setAuthSession(session);
    return { ...session, logged_in_at: new Date().toISOString() };
  },

  async register(input: { email: string; full_name: string; password: string }): Promise<AuthSession> {
    const session = await http<Omit<AuthSession, "logged_in_at">>(endpoints.register, {
      method: "POST",
      body: JSON.stringify(input),
    });
    setAuthSession(session);
    return { ...session, logged_in_at: new Date().toISOString() };
  },

  async forgotPassword(email: string) {
    return http<{ status: string }>(endpoints.forgotPassword, {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },

  async resetPassword(token: string, password: string) {
    return http<{ status: string }>(endpoints.resetPassword, {
      method: "POST",
      body: JSON.stringify({ token, password }),
    });
  },

  async me(): Promise<AuthUser> {
    return http<AuthUser>(endpoints.me);
  },

  async logout() {
    await http(endpoints.logout, { method: "POST", body: JSON.stringify({}) }).catch(() => undefined);
    clearAuthSession();
  },

  async health() {
    return http<{ status: string; service?: string; version?: string }>(endpoints.health);
  },

  async getBrowserGuardActive(): Promise<{ active: boolean }> {
    return http<{ active: boolean }>(endpoints.browserGuardActive);
  },

  async pingBrowserGuard(): Promise<{ status: string; mode?: string }> {
    return http<{ status: string; mode?: string }>(endpoints.browserGuardPing);
  },

  async issueBrowserGuardToken(session_id: string): Promise<{ token: string; session_id: string }> {
    return http<{ token: string; session_id: string }>(endpoints.browserGuardToken, {
      method: "POST",
      body: JSON.stringify({ session_id }),
    });
  },

  async startProctor(input: { session_id: string; student_id?: string; exam_code?: string }) {
    return http<{ status: string; session_id: string }>(endpoints.proctorStart, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  async stopProctor() {
    return http<{ status: string; session_id?: string }>(endpoints.proctorStop, {
      method: "POST",
      body: JSON.stringify({}),
    });
  },

  async getProctorStatus(): Promise<ProctorStatus> {
    return http<ProctorStatus>(endpoints.proctorStatus);
  },

  async postBrowserSignal(endpoint: string, payload: Record<string, unknown>): Promise<void> {
    await http(endpoint, { method: "POST", body: JSON.stringify(payload) }).catch(() => undefined);
  },

  async checkCameraStream(source: "primary" | "secondary" = "primary"): Promise<boolean> {
    if (typeof window === "undefined") return false;
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 1800);
    try {
      const res = await fetch(`${VIDEO_BASE_URL}${endpoints.cameraStream("", source)}`, {
        method: "GET",
        signal: controller.signal,
      });
      return res.ok;
    } catch {
      return false;
    } finally {
      window.clearTimeout(timeout);
    }
  },

  async getExams(): Promise<Exam[]> {
    const raw = await http<any[]>(endpoints.studentExams);
    return raw.map(mapBackendExam);
  },

  async getInstructorExams(): Promise<Exam[]> {
    const raw = await http<any[]>(endpoints.exams);
    return raw.map(mapBackendExam);
  },

  async createExam(input: any): Promise<Exam> {
    const raw = await http<any>(endpoints.exams, { method: "POST", body: JSON.stringify(input) });
    return mapBackendExam(raw);
  },

  async updateExam(id: string, input: any): Promise<Exam> {
    const raw = await http<any>(endpoints.exam(id), { method: "PUT", body: JSON.stringify(input) });
    return mapBackendExam(raw);
  },

  async publishExam(id: string): Promise<Exam> {
    const raw = await http<any>(endpoints.examPublish(id), { method: "POST", body: JSON.stringify({}) });
    return mapBackendExam(raw);
  },

  async getExamQuestions(examId: string): Promise<ExamQuestion[]> {
    const raw = await http<any[]>(endpoints.examQuestions(examId));
    return raw.map(mapBackendQuestion);
  },

  async saveExamQuestion(examId: string, input: Partial<ExamQuestion>): Promise<ExamQuestion> {
    const isUpdate = !!input.question_id;
    const raw = await http<any>(
      isUpdate ? endpoints.examQuestion(examId, input.question_id as string) : endpoints.examQuestions(examId),
      {
        method: isUpdate ? "PUT" : "POST",
        body: JSON.stringify(input),
      },
    );
    return mapBackendQuestion(raw);
  },

  async deleteExamQuestion(examId: string, questionId: string): Promise<{ status: string }> {
    return http<{ status: string }>(endpoints.examQuestion(examId, questionId), { method: "DELETE" });
  },

  async assignExam(examId: string, student_email: string) {
    return http<any>(endpoints.examAssignments(examId), {
      method: "POST",
      body: JSON.stringify({ student_email }),
    });
  },

  async getExamAssignments(examId: string): Promise<ExamAssignment[]> {
    return http<ExamAssignment[]>(endpoints.examAssignments(examId));
  },

  async revokeExamAssignment(examId: string, assignmentId: string) {
    return http<{ status: string; assignment_id: string }>(endpoints.examAssignment(examId, assignmentId), {
      method: "DELETE",
    });
  },

  async getExamAttendance(examId: string): Promise<ExamAttendanceRow[]> {
    return http<ExamAttendanceRow[]>(endpoints.examAttendance(examId));
  },

  async getExamAttempts(examId: string): Promise<ExamAttempt[]> {
    const raw = await http<any[]>(endpoints.examAttempts(examId));
    return raw.map(mapBackendAttempt);
  },

  async joinExamByCode(exam_code: string): Promise<Exam> {
    const raw = await http<any>(endpoints.studentExamJoinCode, {
      method: "POST",
      body: JSON.stringify({ exam_code }),
    });
    return mapBackendExam(raw);
  },

  async startAttempt(input: { exam_id: string; roll_number: string; session_id?: string }): Promise<ExamAttempt> {
    const raw = await http<any>(endpoints.attemptsStart, {
      method: "POST",
      body: JSON.stringify(input),
    });
    return mapBackendAttempt(raw);
  },

  async getAttempt(id: string): Promise<ExamAttempt> {
    const raw = await http<any>(endpoints.attempt(id));
    return mapBackendAttempt(raw);
  },

  async saveAttemptResponse(id: string, input: { question_id: string; selected_option_id?: string; response_text?: string }) {
    return http<any>(endpoints.attemptResponses(id), {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  async submitAttempt(id: string): Promise<ExamAttempt> {
    const raw = await http<any>(endpoints.attemptSubmit(id), {
      method: "POST",
      body: JSON.stringify({ generate_report: true }),
    });
    return mapBackendAttempt(raw);
  },

  async getDashboard(role: "student" | "instructor" | "admin") {
    const endpoint =
      role === "admin" ? endpoints.dashboardAdmin : role === "instructor" ? endpoints.dashboardInstructor : endpoints.dashboardStudent;
    return http<any>(endpoint);
  },

  async getSettings() {
    return http<Record<string, any>>(endpoints.settings);
  },

  async saveSettings(values: Record<string, any>) {
    return http<Record<string, any>>(endpoints.settings, {
      method: "PUT",
      body: JSON.stringify({ values }),
    });
  },

  async getTenants(): Promise<Tenant[]> {
    return http<Tenant[]>(endpoints.tenants);
  },

  async createTenant(input: { name: string; slug: string; plan_name?: string; settings?: Record<string, unknown> }): Promise<Tenant> {
    return http<Tenant>(endpoints.tenants, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  async updateTenant(id: string, input: { name: string; slug: string; status: string; plan_name?: string; settings?: Record<string, unknown> }): Promise<Tenant> {
    return http<Tenant>(endpoints.tenant(id), {
      method: "PUT",
      body: JSON.stringify(input),
    });
  },

  async getAuditLogs(limit = 100): Promise<AuditLog[]> {
    return http<AuditLog[]>(`${endpoints.auditLogs}?limit=${limit}`);
  },

  async getAdminUsers(params: { tenant_id?: string; role?: string; q?: string; limit?: number } = {}): Promise<AdminUser[]> {
    const search = new URLSearchParams();
    if (params.tenant_id) search.set("tenant_id", params.tenant_id);
    if (params.role) search.set("role", params.role);
    if (params.q) search.set("q", params.q);
    if (params.limit) search.set("limit", String(params.limit));
    const suffix = search.toString() ? `?${search}` : "";
    return http<AdminUser[]>(`${endpoints.adminUsers}${suffix}`);
  },

  async createAdminUser(input: {
    email: string;
    full_name: string;
    role: "student" | "instructor" | "admin";
    tenant_id: string;
    password: string;
  }): Promise<AdminUser> {
    return http<AdminUser>(endpoints.adminUsers, {
      method: "POST",
      body: JSON.stringify(input),
    });
  },

  async updateAdminUser(
    id: string,
    input: Partial<Pick<AdminUser, "full_name" | "role" | "tenant_id" | "is_active">>,
  ): Promise<AdminUser> {
    return http<AdminUser>(endpoints.adminUser(id), {
      method: "PUT",
      body: JSON.stringify(input),
    });
  },

  async setAdminUserPassword(id: string, password: string): Promise<{ status: string; user_id: string }> {
    return http<{ status: string; user_id: string }>(endpoints.adminUserPassword(id), {
      method: "POST",
      body: JSON.stringify({ password }),
    });
  },

  async startSession(input: {
    session_id?: string;
    student_id?: string;
    student_name?: string;
    exam_code?: string;
    exam_id?: string;
  }): Promise<{ status: string; session_id: string }> {
    const session_id =
      input.session_id ||
      `SESSION_${Date.now().toString(36).toUpperCase()}_${Math.random().toString(36).slice(2, 6).toUpperCase()}`;
    return http<{ status: string; session_id: string }>(endpoints.sessionsStart, {
      method: "POST",
      body: JSON.stringify({ ...input, session_id }),
    });
  },

  async endSession(id: string) {
    return http<{ status: string; session_id: string }>(endpoints.sessionEnd(id), {
      method: "POST",
      body: JSON.stringify({ generate_report: true }),
    });
  },

  async getSessions(): Promise<Session[]> {
    const rawList = await http<any[]>(endpoints.sessions);
    return rawList.map(mapBackendSessionSummaryToSession);
  },

  async getSession(id: string): Promise<SessionDetail> {
    const raw = await http<any>(endpoints.session(id));
    const base = mapBackendSessionSummaryToSession(raw);
    const events = raw.events?.length ? raw.events.map(mapBackendEventToSessionEvent) : await api.getEvents(id).catch(() => []);
    const [evidence, browser_activity, audio_events, risk] = await Promise.all([
      api.getEvidence(id).catch(() => []),
      api.getBrowserActivity(id).catch(() => []),
      api.getAudio(id).catch(() => []),
      api.getRisk(id).catch(() => ({
        session_id: id,
        score: base.risk_score,
        level: base.risk_level,
        trend: [],
        contributors: [],
        updated_at: new Date().toISOString(),
      })),
    ]);
    return {
      ...base,
      events,
      events_count: raw.event_count ?? events.length,
      evidence,
      evidence_count: evidence.length,
      browser_activity,
      browser_guard_active: browser_activity.length > 0,
      audio_events,
      risk,
      risk_score: risk.score,
      risk_level: risk.level,
    };
  },

  async getEvents(id: string): Promise<SessionEvent[]> {
    const raw = await http<any[]>(endpoints.sessionEvents(id));
    return raw.map(mapBackendEventToSessionEvent);
  },

  async getRisk(id: string): Promise<RiskScore> {
    const [raw, trendRaw] = await Promise.all([
      http<any>(endpoints.sessionRisk(id)),
      http<any[]>(endpoints.sessionRiskTrend(id)).catch(() => []),
    ]);
    return {
      session_id: raw.session_id,
      score: raw.risk_score,
      level: mapRiskLevel(raw.risk_score),
      trend: trendRaw.map((t) => ({ t: t.timestamp, score: t.score })),
      contributors: (raw.contributors || []).map((c: any, i: number) => ({
        id: `${id}-risk-${i}`,
        label: c.event_type,
        delta: c.points,
        category:
          inferEventCategory(c.event_type) === "audio_voice"
            ? "audio"
            : ["tab_switch", "url_visit", "fullscreen_exit", "browser_guard"].includes(inferEventCategory(c.event_type))
              ? "browser"
              : inferEventCategory(c.event_type) === "phone_detected"
                ? "phone"
                : ["face_missing", "multiple_faces"].includes(inferEventCategory(c.event_type))
                  ? "face"
                  : inferEventCategory(c.event_type) === "gaze_away"
                    ? "gaze"
                    : "other",
      })),
      updated_at: new Date().toISOString(),
    };
  },

  async getEvidence(id: string): Promise<EvidenceItem[]> {
    const raw = await http<any[]>(endpoints.sessionEvidence(id));
    return raw.map((item) => mapBackendEvidenceToEvidenceItem(item, id));
  },

  async createEvidence(input: { session_id: string; evidence_type: string; label?: string; image_data?: string; filepath?: string }) {
    return http<any>(endpoints.evidenceCreate, { method: "POST", body: JSON.stringify(input) });
  },

  async getBrowserActivity(id: string): Promise<BrowserActivity[]> {
    const raw = await http<any[]>(endpoints.sessionBrowserActivity(id));
    return raw.map(mapBackendBrowserActivityToBrowserActivity);
  },

  async getAudio(id: string): Promise<AudioEvent[]> {
    const raw = await http<any[]>(endpoints.sessionAudio(id)).catch(() => []);
    return raw.map(mapBackendAudioToAudioEvent);
  },

  async getReport(id: string): Promise<Report> {
    const raw = await http<any>(endpoints.sessionReport(id));
    return {
      id: raw.session_id,
      session_id: raw.session_id,
      generated_at: raw.generated_at || new Date().toISOString(),
      verdict: raw.risk_level || mapRiskLevel(Number(raw.risk_score || 0)),
      summary: raw.summary || "Report metadata fetched.",
      pdf_url: raw.pdf_url ? resolveBackendUrl(raw.pdf_url) : `${API_BASE_URL}${endpoints.sessionReportDownload(id)}`,
    };
  },

  async generateReport(session_id: string): Promise<Report> {
    const raw = await http<any>(endpoints.reportsGenerate, {
      method: "POST",
      body: JSON.stringify({ session_id }),
    });
    return {
      id: raw.session_id,
      session_id: raw.session_id,
      generated_at: raw.generated_at || new Date().toISOString(),
      verdict: raw.risk_level || mapRiskLevel(Number(raw.risk_score || 0)),
      summary: raw.summary || "Report generated.",
      pdf_url: raw.pdf_url ? resolveBackendUrl(raw.pdf_url) : `${API_BASE_URL}${endpoints.sessionReportDownload(session_id)}`,
    };
  },

  async downloadReport(sessionId: string): Promise<void> {
    const response = await fetch(`${API_BASE_URL}${endpoints.sessionReportDownload(sessionId)}`, {
      headers: authHeaders(),
    });
    if (!response.ok) throw new Error(`Report download failed (${response.status}).`);
    const blobUrl = URL.createObjectURL(await response.blob());
    const link = document.createElement("a");
    link.href = blobUrl;
    link.download = `${sessionId}_report.pdf`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(blobUrl), 1000);
  },

  async submitReview(id: string, payload: ReviewSubmission): Promise<{ ok: true }> {
    let mark = "Pending Review";
    if (payload.decision === "valid") mark = "Valid";
    if (payload.decision === "false_positive") mark = "False Positive";
    if (payload.decision === "dismissed") mark = "Dismissed";
    if (payload.decision === "needs_review") mark = "Needs Review";
    await http(endpoints.sessionReview(id), {
      method: "POST",
      body: JSON.stringify({ review_mark: mark, instructor_notes: payload.notes ?? "" }),
    });
    return { ok: true };
  },

  async assistantQuery(req: AssistantQueryRequest): Promise<AssistantQueryResponse> {
    const raw = await http<any>(endpoints.assistantQuery, {
      method: "POST",
      body: JSON.stringify({ query: req.query, role: req.mode, context: { session_id: req.session_id } }),
    });
    return {
      reply: raw.answer,
      quick_actions: raw.quick_actions ?? [],
      references: raw.references ?? [],
      confidence: raw.confidence,
      intent: raw.intent,
    };
  },

  cameraStreamUrl(sessionId: string, source: "primary" | "secondary" = "primary", token?: string | null) {
    if (!sessionId || !token) return null;
    return `${VIDEO_BASE_URL}${endpoints.cameraStream("", source)}?token=${encodeURIComponent(token)}`;
  },
};
