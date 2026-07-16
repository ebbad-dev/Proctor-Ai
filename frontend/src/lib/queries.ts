import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./api";
import type { ReviewSubmission } from "./types";

export const qk = {
  health: ["health"] as const,
  sessions: ["sessions"] as const,
  session: (id: string) => ["session", id] as const,
  risk: (id: string) => ["session", id, "risk"] as const,
  events: (id: string) => ["session", id, "events"] as const,
  evidence: (id: string) => ["session", id, "evidence"] as const,
  browser: (id: string) => ["session", id, "browser"] as const,
  audio: (id: string) => ["session", id, "audio"] as const,
  report: (id: string) => ["session", id, "report"] as const,
  exams: ["exams"] as const,
  instructorExams: ["instructor-exams"] as const,
  examQuestions: (examId: string) => ["exam", examId, "questions"] as const,
  examAssignments: (examId: string) => ["exam", examId, "assignments"] as const,
  examAttendance: (examId: string) => ["exam", examId, "attendance"] as const,
  examAttempts: (examId: string) => ["exam", examId, "attempts"] as const,
  attempt: (id: string) => ["attempt", id] as const,
  dashboard: (role: string) => ["dashboard", role] as const,
  settings: ["settings"] as const,
  tenants: ["tenants"] as const,
  adminUsers: (params?: Record<string, unknown>) => ["admin-users", params ?? {}] as const,
  auditLogs: ["audit-logs"] as const,
  browserGuard: ["browser-guard"] as const,
  proctorStatus: ["proctor-status"] as const,
  camera: (source: "primary" | "secondary") => ["camera", source] as const,
};

export function useHealth() {
  return useQuery({ queryKey: qk.health, queryFn: () => api.health(), retry: 1 });
}

export function useSessions() {
  return useQuery({ queryKey: qk.sessions, queryFn: () => api.getSessions() });
}

export function useSession(id: string) {
  return useQuery({ queryKey: qk.session(id), queryFn: () => api.getSession(id), enabled: !!id });
}

// Live risk: poll every 3s — swap to WS/SSE later
export function useLiveRisk(id: string) {
  return useQuery({
    queryKey: qk.risk(id),
    queryFn: () => api.getRisk(id),
    refetchInterval: 3000,
    enabled: !!id,
  });
}

export function useEvents(id: string, refetchMs = 5000) {
  return useQuery({
    queryKey: qk.events(id),
    queryFn: () => api.getEvents(id),
    refetchInterval: refetchMs,
    enabled: !!id,
  });
}

export function useEvidence(id: string) {
  return useQuery({ queryKey: qk.evidence(id), queryFn: () => api.getEvidence(id), enabled: !!id });
}

export function useBrowserActivity(id: string) {
  return useQuery({
    queryKey: qk.browser(id),
    queryFn: () => api.getBrowserActivity(id),
    refetchInterval: 3000,
    enabled: !!id,
  });
}

export function useAudio(id: string) {
  return useQuery({
    queryKey: qk.audio(id),
    queryFn: () => api.getAudio(id),
    refetchInterval: 3000,
    enabled: !!id,
  });
}

export function useReport(id: string) {
  return useQuery({
    queryKey: qk.report(id),
    queryFn: () => api.getReport(id),
    enabled: !!id,
    retry: false,
  });
}

export function useExams() {
  return useQuery({ queryKey: qk.exams, queryFn: () => api.getExams() });
}

export function useInstructorExams() {
  return useQuery({ queryKey: qk.instructorExams, queryFn: () => api.getInstructorExams() });
}

export function useDashboard(role: "student" | "instructor" | "admin") {
  return useQuery({ queryKey: qk.dashboard(role), queryFn: () => api.getDashboard(role) });
}

export function useSettings() {
  return useQuery({ queryKey: qk.settings, queryFn: () => api.getSettings() });
}

export function useSaveSettings() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (values: Record<string, unknown>) => api.saveSettings(values),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.settings }),
  });
}

export function useTenants() {
  return useQuery({ queryKey: qk.tenants, queryFn: () => api.getTenants() });
}

export function useCreateTenant() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { name: string; slug: string; plan_name?: string; settings?: Record<string, unknown> }) =>
      api.createTenant(input),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.tenants }),
  });
}

export function useAuditLogs() {
  return useQuery({
    queryKey: qk.auditLogs,
    queryFn: () => api.getAuditLogs(100),
    refetchInterval: 10000,
  });
}

export function useAdminUsers(params: { tenant_id?: string; role?: string; q?: string } = {}) {
  return useQuery({ queryKey: qk.adminUsers(params), queryFn: () => api.getAdminUsers(params) });
}

export function useCreateAdminUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      email: string;
      full_name: string;
      role: "student" | "instructor" | "admin";
      tenant_id: string;
      password: string;
    }) => api.createAdminUser(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      qc.invalidateQueries({ queryKey: qk.auditLogs });
      qc.invalidateQueries({ queryKey: qk.dashboard("admin") });
    },
  });
}

export function useUpdateAdminUser() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      user_id: string;
      values: {
        full_name?: string;
        role?: "student" | "instructor" | "admin";
        tenant_id?: string;
        is_active?: boolean;
      };
    }) => api.updateAdminUser(input.user_id, input.values),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["admin-users"] });
      qc.invalidateQueries({ queryKey: qk.auditLogs });
      qc.invalidateQueries({ queryKey: qk.dashboard("admin") });
    },
  });
}

export function useSetAdminUserPassword() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { user_id: string; password: string }) =>
      api.setAdminUserPassword(input.user_id, input.password),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.auditLogs }),
  });
}

export function useCreateExam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: Record<string, unknown>) => api.createExam(input),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.exams });
      qc.invalidateQueries({ queryKey: qk.instructorExams });
      qc.invalidateQueries({ queryKey: qk.dashboard("instructor") });
      qc.invalidateQueries({ queryKey: qk.dashboard("admin") });
    },
  });
}

export function useUpdateExam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { exam_id: string; values: Record<string, unknown> }) =>
      api.updateExam(input.exam_id, input.values),
    onSuccess: (_data, input) => {
      qc.invalidateQueries({ queryKey: qk.instructorExams });
      qc.invalidateQueries({ queryKey: qk.examAssignments(input.exam_id) });
      qc.invalidateQueries({ queryKey: qk.dashboard("instructor") });
      qc.invalidateQueries({ queryKey: qk.dashboard("admin") });
    },
  });
}

export function usePublishExam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (examId: string) => api.publishExam(examId),
    onSuccess: (_data, examId) => {
      qc.invalidateQueries({ queryKey: qk.instructorExams });
      qc.invalidateQueries({ queryKey: qk.examQuestions(examId) });
      qc.invalidateQueries({ queryKey: qk.dashboard("instructor") });
    },
  });
}

export function useExamQuestions(examId: string) {
  return useQuery({
    queryKey: qk.examQuestions(examId),
    queryFn: () => api.getExamQuestions(examId),
    enabled: !!examId,
  });
}

export function useSaveExamQuestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { exam_id: string; values: Record<string, unknown> }) =>
      api.saveExamQuestion(input.exam_id, input.values as any),
    onSuccess: (_data, input) => {
      qc.invalidateQueries({ queryKey: qk.examQuestions(input.exam_id) });
      qc.invalidateQueries({ queryKey: qk.instructorExams });
    },
  });
}

export function useDeleteExamQuestion() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { exam_id: string; question_id: string }) =>
      api.deleteExamQuestion(input.exam_id, input.question_id),
    onSuccess: (_data, input) => {
      qc.invalidateQueries({ queryKey: qk.examQuestions(input.exam_id) });
      qc.invalidateQueries({ queryKey: qk.instructorExams });
    },
  });
}

export function useExamAssignments(examId: string) {
  return useQuery({
    queryKey: qk.examAssignments(examId),
    queryFn: () => api.getExamAssignments(examId),
    enabled: !!examId,
  });
}

export function useAssignExam() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { exam_id: string; student_email: string }) =>
      api.assignExam(input.exam_id, input.student_email),
    onSuccess: (_data, input) => {
      qc.invalidateQueries({ queryKey: qk.examAssignments(input.exam_id) });
      qc.invalidateQueries({ queryKey: qk.instructorExams });
      qc.invalidateQueries({ queryKey: qk.auditLogs });
    },
  });
}

export function useRevokeExamAssignment() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { exam_id: string; assignment_id: string }) =>
      api.revokeExamAssignment(input.exam_id, input.assignment_id),
    onSuccess: (_data, input) => {
      qc.invalidateQueries({ queryKey: qk.examAssignments(input.exam_id) });
      qc.invalidateQueries({ queryKey: qk.instructorExams });
      qc.invalidateQueries({ queryKey: qk.auditLogs });
    },
  });
}

export function useExamAttendance(examId: string) {
  return useQuery({
    queryKey: qk.examAttendance(examId),
    queryFn: () => api.getExamAttendance(examId),
    enabled: !!examId,
    refetchInterval: 10000,
  });
}

export function useExamAttempts(examId: string) {
  return useQuery({
    queryKey: qk.examAttempts(examId),
    queryFn: () => api.getExamAttempts(examId),
    enabled: !!examId,
  });
}

export function useJoinExamByCode() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (exam_code: string) => api.joinExamByCode(exam_code),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.exams });
      qc.invalidateQueries({ queryKey: qk.dashboard("student") });
    },
  });
}

export function useStartAttempt() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { exam_id: string; roll_number: string; session_id?: string }) => api.startAttempt(input),
    onSuccess: (attempt) => {
      qc.invalidateQueries({ queryKey: qk.attempt(attempt.attempt_id) });
      qc.invalidateQueries({ queryKey: qk.sessions });
    },
  });
}

export function useAttempt(id: string) {
  return useQuery({
    queryKey: qk.attempt(id),
    queryFn: () => api.getAttempt(id),
    enabled: !!id,
    refetchInterval: 10000,
  });
}

export function useSaveAttemptResponse(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: { question_id: string; selected_option_id?: string; response_text?: string }) =>
      api.saveAttemptResponse(id, input),
    onSuccess: () => qc.invalidateQueries({ queryKey: qk.attempt(id) }),
  });
}

export function useSubmitAttempt(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.submitAttempt(id),
    onSuccess: (attempt) => {
      qc.invalidateQueries({ queryKey: qk.attempt(id) });
      qc.invalidateQueries({ queryKey: qk.sessions });
      if (attempt.session_id) {
        qc.invalidateQueries({ queryKey: qk.session(attempt.session_id) });
      }
    },
  });
}

export function useCreateEvidence() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (input: {
      session_id: string;
      evidence_type: string;
      label?: string;
      image_data?: string;
      filepath?: string;
    }) => api.createEvidence(input),
    onSuccess: (_data, input) => {
      qc.invalidateQueries({ queryKey: qk.evidence(input.session_id) });
      qc.invalidateQueries({ queryKey: qk.session(input.session_id) });
    },
  });
}

export function useEndSession(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.endSession(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.session(id) });
      qc.invalidateQueries({ queryKey: qk.sessions });
      qc.invalidateQueries({ queryKey: qk.report(id) });
    },
  });
}

export function useBrowserGuardActive() {
  return useQuery({
    queryKey: qk.browserGuard,
    queryFn: () => api.getBrowserGuardActive(),
    refetchInterval: 5000,
  });
}

export function useProctorStatus() {
  return useQuery({
    queryKey: qk.proctorStatus,
    queryFn: () => api.getProctorStatus(),
    refetchInterval: 2500,
  });
}

export function useCameraStreamHealth(source: "primary" | "secondary") {
  return useQuery({
    queryKey: qk.camera(source),
    queryFn: () => api.checkCameraStream(source),
    refetchInterval: 8000,
  });
}

export function useGenerateReport(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: () => api.generateReport(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.report(id) });
      qc.invalidateQueries({ queryKey: qk.session(id) });
    },
  });
}

export function useSubmitReview(id: string) {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (payload: ReviewSubmission) => api.submitReview(id, payload),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: qk.session(id) });
      qc.invalidateQueries({ queryKey: qk.sessions });
    },
  });
}
