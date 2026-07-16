import { createFileRoute, Link } from "@tanstack/react-router";
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/common/GlassCard";
import { GlowButton } from "@/components/common/GlowButton";
import { StatusBadge } from "@/components/common/StatusBadge";
import {
  useAssignExam,
  useCreateExam,
  useDashboard,
  useDeleteExamQuestion,
  useExamAssignments,
  useExamAttendance,
  useExamQuestions,
  useInstructorExams,
  usePublishExam,
  useRevokeExamAssignment,
  useSaveExamQuestion,
  useSessions,
  useUpdateExam,
} from "@/lib/queries";
import {
  BarChart,
  Bar,
  ResponsiveContainer,
  XAxis,
  YAxis,
  Tooltip,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { Search, Download, ExternalLink, ClipboardList, Save, UserPlus, X, Plus, Send, Trash2 } from "lucide-react";
import type { Exam, ExamAttendanceRow, ExamQuestion, RiskLevel } from "@/lib/types";
import { cn } from "@/lib/utils";
import { NoSessions } from "@/components/common/States";
import { getAuthSession } from "@/lib/auth";

export const Route = createFileRoute("/instructor")({
  validateSearch: (s: Record<string, unknown>) => ({
    risk: (s.risk as RiskLevel | "all" | undefined) ?? undefined,
  }),
  head: () => ({
    meta: [
      { title: "Instructor Dashboard · ProctorAI" },
      {
        name: "description",
        content: "Enterprise dashboard for proctoring sessions, risk distribution, and reviews.",
      },
    ],
  }),
  component: InstructorPage,
});

const riskColor: Record<RiskLevel, string> = {
  low: "oklch(0.72 0.18 155)",
  medium: "oklch(0.78 0.18 75)",
  high: "oklch(0.7 0.2 35)",
  critical: "oklch(0.6 0.26 20)",
};

function InstructorPage() {
  const sessions = useSessions();
  const search = Route.useSearch();
  const [q, setQ] = useState("");
  const [filter, setFilter] = useState<"all" | RiskLevel>(search.risk ?? "all");
  const [sort, setSort] = useState<"risk" | "time">("risk");
  const role = getAuthSession()?.user.role ?? "instructor";
  const dashboard = useDashboard(role === "admin" ? "admin" : "instructor");

  const data = useMemo(() => sessions.data ?? [], [sessions.data]);
  const filtered = useMemo(() => {
    let arr = data.filter(
      (s) =>
        (filter === "all" || s.risk_level === filter) &&
        (q === "" ||
          s.student.name.toLowerCase().includes(q.toLowerCase()) ||
          s.exam.title.toLowerCase().includes(q.toLowerCase())),
    );
    arr = [...arr].sort((a, b) =>
      sort === "risk"
        ? b.risk_score - a.risk_score
        : new Date(b.started_at).getTime() - new Date(a.started_at).getTime(),
    );
    return arr;
  }, [data, q, filter, sort]);

  const kpis = useMemo(() => {
    const high = data.filter((s) => s.risk_level === "high" || s.risk_level === "critical").length;
    return [
      { label: "Total sessions", value: dashboard.data?.total_sessions ?? data.length },
      { label: "High-risk", value: dashboard.data?.high_risk_sessions ?? high, tone: "danger" as const },
      { label: "Pending review", value: data.filter((s) => s.review_status === "pending").length },
      { label: "Total exams", value: dashboard.data?.total_exams ?? 0 },
    ];
  }, [dashboard.data, data]);

  const pieData = (["low", "medium", "high", "critical"] as RiskLevel[]).map((lvl) => ({
    name: lvl,
    value: data.filter((s) => s.risk_level === lvl).length || 0,
  }));

  const barData = useMemo(() => {
    const buckets = new Map<string, number>();
    for (const event of dashboard.data?.recent_activity ?? []) {
      const hour = new Date(event.event_time).toLocaleTimeString([], { hour: "2-digit" });
      buckets.set(hour, (buckets.get(hour) ?? 0) + 1);
    }
    return [...buckets.entries()].map(([t, events]) => ({ t, events }));
  }, [dashboard.data]);

  return (
    <AppShell>
      <div className="space-y-4">
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          className="grid grid-cols-2 gap-3 md:grid-cols-4"
        >
          {kpis.map((k, i) => (
            <motion.div
              key={k.label}
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: i * 0.05 }}
            >
              <GlassCard className="p-4">
                <div className="text-[11px] uppercase tracking-wider text-muted-foreground">
                  {k.label}
                </div>
                <div
                  className={cn("mt-1 text-3xl font-bold", k.tone === "danger" && "text-red-300")}
                >
                  {k.value}
                </div>
              </GlassCard>
            </motion.div>
          ))}
        </motion.div>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <GlassCard className="p-4">
            <h3 className="text-sm font-semibold">Risk distribution</h3>
            <div className="mt-2 h-56">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={pieData}
                    dataKey="value"
                    nameKey="name"
                    innerRadius={50}
                    outerRadius={80}
                    stroke="oklch(0.16 0.03 260)"
                  >
                    {pieData.map((d) => (
                      <Cell key={d.name} fill={riskColor[d.name as RiskLevel]} />
                    ))}
                  </Pie>
                  <Tooltip
                    contentStyle={{
                      background: "oklch(0.2 0.03 260 / 0.9)",
                      border: "1px solid oklch(1 0 0 / 0.1)",
                      borderRadius: 12,
                      color: "white",
                      fontSize: 12,
                    }}
                  />
                </PieChart>
              </ResponsiveContainer>
            </div>
            <div className="mt-2 flex flex-wrap items-center justify-center gap-3 text-[11px]">
              {pieData.map((p) => (
                <span key={p.name} className="flex items-center gap-1.5 text-muted-foreground">
                  <span
                    className="h-2 w-2 rounded-full"
                    style={{ background: riskColor[p.name as RiskLevel] }}
                  />
                  {p.name} · {p.value}
                </span>
              ))}
            </div>
          </GlassCard>

          <GlassCard className="p-4">
            <h3 className="text-sm font-semibold">Event frequency</h3>
            <div className="mt-2 h-56">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={barData}>
                  <XAxis
                    dataKey="t"
                    tick={{ fontSize: 11, fill: "oklch(0.7 0.02 250)" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    tick={{ fontSize: 11, fill: "oklch(0.7 0.02 250)" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "oklch(0.2 0.03 260 / 0.9)",
                      border: "1px solid oklch(1 0 0 / 0.1)",
                      borderRadius: 12,
                      color: "white",
                      fontSize: 12,
                    }}
                  />
                  <Bar dataKey="events" radius={[8, 8, 0, 0]} fill="oklch(0.78 0.16 215)" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </GlassCard>
        </div>

        <ExamManagement />

        <GlassCard className="p-3">
          <div className="flex flex-wrap items-center gap-2 p-2">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <input
                value={q}
                onChange={(e) => setQ(e.target.value)}
                placeholder="Search students or exams"
                className="h-9 w-64 rounded-lg border border-white/10 bg-white/5 pl-9 pr-3 text-sm outline-none placeholder:text-muted-foreground focus:border-primary/40"
              />
            </div>
            <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 p-0.5">
              {(["all", "low", "medium", "high", "critical"] as const).map((f) => (
                <button
                  key={f}
                  onClick={() => setFilter(f)}
                  className={cn(
                    "rounded-md px-2.5 py-1 text-xs capitalize transition-colors",
                    filter === f
                      ? "bg-white/10 text-foreground"
                      : "text-muted-foreground hover:text-foreground",
                  )}
                >
                  {f}
                </button>
              ))}
            </div>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as "risk" | "time")}
              className="h-9 rounded-lg border border-white/10 bg-white/5 px-2 text-xs outline-none"
            >
              <option value="risk">Sort: risk score</option>
              <option value="time">Sort: most recent</option>
            </select>
            <GlowButton variant="ghost" size="sm" className="ml-auto">
              <Download className="h-4 w-4" /> Export
            </GlowButton>
          </div>

          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-sm">
              <thead>
                <tr className="text-left text-[11px] uppercase tracking-wider text-muted-foreground">
                  <Th>Student</Th>
                  <Th>Exam</Th>
                  <Th>Risk</Th>
                  <Th>Browser Guard</Th>
                  <Th>Evidence</Th>
                  <Th>Review</Th>
                  <Th> </Th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((s, i) => (
                  <motion.tr
                    key={s.id}
                    initial={{ opacity: 0, y: 6 }}
                    animate={{ opacity: 1, y: 0 }}
                    transition={{ delay: i * 0.02 }}
                    className="border-t border-white/5 transition-colors hover:bg-white/5"
                  >
                    <Td>
                      <div className="font-medium">{s.student.name}</div>
                      <div className="text-[11px] text-muted-foreground">{s.student.email}</div>
                    </Td>
                    <Td>{s.exam.title}</Td>
                    <Td>
                      <div className="flex items-center gap-2">
                        <span className="font-mono">{s.risk_score}</span>
                        <StatusBadge label={s.risk_level} level={s.risk_level} />
                      </div>
                    </Td>
                    <Td>
                      <StatusBadge
                        label={s.browser_guard_active ? "Active" : "Inactive"}
                        status={s.browser_guard_active ? "ok" : "warning"}
                      />
                    </Td>
                    <Td>
                      <span className="font-mono text-muted-foreground">{s.evidence_count}</span>
                    </Td>
                    <Td>
                      <span
                        className={cn(
                          "rounded-md px-2 py-1 text-[11px] capitalize",
                          s.review_status === "pending"
                            ? "bg-amber-400/10 text-amber-300"
                            : "bg-emerald-400/10 text-emerald-300",
                        )}
                      >
                        {s.review_status.replace("_", " ")}
                      </span>
                    </Td>
                    <Td>
                      <div className="flex items-center justify-end gap-1.5">
                        <Link to="/sessions/$sessionId" params={{ sessionId: s.id }}>
                          <GlowButton variant="ghost" size="sm">
                            Review <ExternalLink className="h-3.5 w-3.5" />
                          </GlowButton>
                        </Link>
                      </div>
                    </Td>
                  </motion.tr>
                ))}
              </tbody>
            </table>
            {filtered.length === 0 && (
              <div className="p-4">
                <NoSessions />
              </div>
            )}
          </div>
        </GlassCard>
      </div>
    </AppShell>
  );
}

function ExamManagement() {
  const exams = useInstructorExams();
  const createExam = useCreateExam();
  const updateExam = useUpdateExam();
  const publishExam = usePublishExam();
  const [selectedId, setSelectedId] = useState("");
  const selected = (exams.data ?? []).find((exam) => exam.id === selectedId) ?? exams.data?.[0];
  const [draft, setDraft] = useState({
    title: "",
    exam_code: "",
    description: "",
    semester: "",
    subject: "",
    department: "",
    total_marks: 0,
    duration_minutes: 60,
    status: "draft",
    start_time: "",
    end_time: "",
    rules: "",
  });

  useEffect(() => {
    if (!selected) return;
    setSelectedId((current) => current || selected.id);
    setDraft({
      title: selected.title ?? "",
      exam_code: selected.exam_code ?? "",
      description: selected.description ?? "",
      semester: selected.semester ?? "",
      subject: selected.subject ?? "",
      department: selected.department ?? "",
      total_marks: selected.total_marks ?? 0,
      duration_minutes: selected.duration_minutes ?? 60,
      status: selected.status ?? "draft",
      start_time: toDatetimeLocal(selected.start_time),
      end_time: toDatetimeLocal(selected.end_time),
      rules: stringifyRules(selected.rules),
    });
  }, [selected?.id]);

  const payload = () => ({
    title: draft.title.trim(),
    exam_code: draft.exam_code.trim(),
    description: draft.description.trim(),
    semester: draft.semester.trim(),
    subject: draft.subject.trim(),
    department: draft.department.trim(),
    total_marks: Number(draft.total_marks || 0),
    duration_minutes: Number(draft.duration_minutes || 60),
    status: draft.status,
    start_time: draft.start_time ? new Date(draft.start_time).toISOString() : null,
    end_time: draft.end_time ? new Date(draft.end_time).toISOString() : null,
    rules: parseRules(draft.rules),
  });

  return (
    <GlassCard className="p-4">
      <div className="mb-4 flex flex-wrap items-center gap-2">
        <ClipboardList className="h-4 w-4 text-primary" aria-hidden />
        <h3 className="text-sm font-semibold">Exam management</h3>
        <span className="text-xs text-muted-foreground">
          {exams.data?.length ?? 0} exams
        </span>
      </div>

      <div className="grid gap-4 lg:grid-cols-[0.75fr_1.25fr]">
        <div className="space-y-2">
          {(exams.data ?? []).map((exam) => (
            <button
              key={exam.id}
              type="button"
              onClick={() => {
                setSelectedId(exam.id);
                setDraft({
                  title: exam.title ?? "",
                  exam_code: exam.exam_code ?? "",
                  description: exam.description ?? "",
                  semester: exam.semester ?? "",
                  subject: exam.subject ?? "",
                  department: exam.department ?? "",
                  total_marks: exam.total_marks ?? 0,
                  duration_minutes: exam.duration_minutes ?? 60,
                  status: exam.status ?? "draft",
                  start_time: toDatetimeLocal(exam.start_time),
                  end_time: toDatetimeLocal(exam.end_time),
                  rules: stringifyRules(exam.rules),
                });
              }}
              className={`w-full rounded-xl border p-3 text-left transition ${
                selected?.id === exam.id
                  ? "border-primary/50 bg-primary/10"
                  : "border-white/10 bg-white/[0.03] hover:bg-white/[0.06]"
              }`}
            >
              <div className="flex items-start justify-between gap-2">
                <div>
                  <div className="font-medium">{exam.title}</div>
                  <div className="text-xs text-muted-foreground">
                    {exam.exam_code || "No code"} · {exam.duration_minutes} min · {exam.assignment_count ?? 0} assigned
                  </div>
                </div>
                <span className="rounded-full border border-white/10 bg-white/5 px-2 py-0.5 text-xs capitalize">
                  {exam.status ?? "draft"}
                </span>
              </div>
            </button>
          ))}
          {!exams.isLoading && !exams.data?.length && (
            <div className="rounded-xl border border-white/10 bg-white/[0.03] p-4 text-sm text-muted-foreground">
              No exams yet. Create the first exam from the form.
            </div>
          )}
        </div>

        <div className="space-y-3">
          <div className="grid gap-2 md:grid-cols-[1fr_140px_130px_150px]">
            <input
              aria-label="Exam title"
              value={draft.title}
              onChange={(event) => setDraft((current) => ({ ...current, title: event.target.value }))}
              placeholder="Exam title"
              className="h-10 rounded-lg border border-white/10 bg-white/5 px-3 text-sm outline-none placeholder:text-muted-foreground focus:border-primary/40"
            />
            <input
              aria-label="Exam code"
              value={draft.exam_code}
              onChange={(event) => setDraft((current) => ({ ...current, exam_code: event.target.value.toUpperCase() }))}
              placeholder="Exam code"
              className="h-10 rounded-lg border border-white/10 bg-white/5 px-3 text-sm uppercase outline-none placeholder:text-muted-foreground focus:border-primary/40"
            />
            <input
              aria-label="Duration in minutes"
              value={draft.duration_minutes}
              onChange={(event) => setDraft((current) => ({ ...current, duration_minutes: Number(event.target.value) }))}
              type="number"
              min={1}
              className="h-10 rounded-lg border border-white/10 bg-white/5 px-3 text-sm outline-none focus:border-primary/40"
            />
            <select
              aria-label="Exam status"
              value={draft.status}
              onChange={(event) => setDraft((current) => ({ ...current, status: event.target.value }))}
              className="h-10 rounded-lg border border-white/10 bg-background px-3 text-sm outline-none focus:border-primary/40"
            >
              <option value="draft">Draft</option>
              <option value="scheduled">Scheduled</option>
              <option value="published" disabled>Published (use Publish)</option>
              <option value="closed">Closed</option>
              <option value="archived">Archived</option>
            </select>
          </div>

          <textarea
            value={draft.description}
            onChange={(event) => setDraft((current) => ({ ...current, description: event.target.value }))}
            placeholder="Description"
            rows={2}
            className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:border-primary/40"
          />

          <div className="grid gap-2 md:grid-cols-4">
            <input
              value={draft.semester}
              onChange={(event) => setDraft((current) => ({ ...current, semester: event.target.value }))}
              placeholder="Semester"
              className="h-10 rounded-lg border border-white/10 bg-white/5 px-3 text-sm outline-none placeholder:text-muted-foreground focus:border-primary/40"
            />
            <input
              value={draft.subject}
              onChange={(event) => setDraft((current) => ({ ...current, subject: event.target.value }))}
              placeholder="Subject"
              className="h-10 rounded-lg border border-white/10 bg-white/5 px-3 text-sm outline-none placeholder:text-muted-foreground focus:border-primary/40"
            />
            <input
              value={draft.department}
              onChange={(event) => setDraft((current) => ({ ...current, department: event.target.value }))}
              placeholder="Department"
              className="h-10 rounded-lg border border-white/10 bg-white/5 px-3 text-sm outline-none placeholder:text-muted-foreground focus:border-primary/40"
            />
            <input
              value={draft.total_marks}
              onChange={(event) => setDraft((current) => ({ ...current, total_marks: Number(event.target.value) }))}
              type="number"
              min={0}
              placeholder="Total marks"
              className="h-10 rounded-lg border border-white/10 bg-white/5 px-3 text-sm outline-none placeholder:text-muted-foreground focus:border-primary/40"
            />
          </div>

          <div className="grid gap-2 md:grid-cols-2">
            <label className="text-xs text-muted-foreground">
              Start time
              <input
                value={draft.start_time}
                onChange={(event) => setDraft((current) => ({ ...current, start_time: event.target.value }))}
                type="datetime-local"
                className="mt-1 h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-foreground outline-none focus:border-primary/40"
              />
            </label>
            <label className="text-xs text-muted-foreground">
              End time
              <input
                value={draft.end_time}
                onChange={(event) => setDraft((current) => ({ ...current, end_time: event.target.value }))}
                type="datetime-local"
                className="mt-1 h-10 w-full rounded-lg border border-white/10 bg-white/5 px-3 text-sm text-foreground outline-none focus:border-primary/40"
              />
            </label>
          </div>

          <textarea
            value={draft.rules}
            onChange={(event) => setDraft((current) => ({ ...current, rules: event.target.value }))}
            placeholder="Rules or JSON policy"
            rows={2}
            className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:border-primary/40"
          />

          <div className="flex flex-wrap justify-end gap-2">
            <GlowButton
              variant="ghost"
              disabled={!draft.title.trim() || createExam.isPending}
              onClick={() => createExam.mutate(payload(), { onSuccess: (exam) => setSelectedId(exam.id) })}
            >
              <ClipboardList className="h-4 w-4" />
              {createExam.isPending ? "Creating..." : "Create new"}
            </GlowButton>
            <GlowButton
              disabled={!selected || !draft.title.trim() || updateExam.isPending}
              onClick={() => selected && updateExam.mutate({ exam_id: selected.id, values: payload() })}
            >
              <Save className="h-4 w-4" />
              {updateExam.isPending ? "Saving..." : "Save changes"}
            </GlowButton>
            <GlowButton
              variant="outline"
              disabled={!selected || publishExam.isPending}
              onClick={() => selected && publishExam.mutate(selected.id)}
            >
              <Send className="h-4 w-4" />
              {publishExam.isPending ? "Publishing..." : "Publish"}
            </GlowButton>
          </div>
          {(createExam.error || updateExam.error || publishExam.error) && (
            <p className="rounded-lg border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
              {(createExam.error || updateExam.error || publishExam.error)?.message}
            </p>
          )}

          {selected && (
            <>
              <QuestionBuilder exam={selected} />
              <AssignmentPanel exam={selected} />
              <AttendancePanel exam={selected} />
            </>
          )}
        </div>
      </div>
    </GlassCard>
  );
}

function QuestionBuilder({ exam }: { exam: Exam }) {
  const questions = useExamQuestions(exam.id);
  const saveQuestion = useSaveExamQuestion();
  const deleteQuestion = useDeleteExamQuestion();
  const [validationError, setValidationError] = useState("");
  const [draft, setDraft] = useState<{
    question_id: string;
    question_text: string;
    marks: number;
    options: { option_id?: string; option_text: string; is_correct: boolean; sort_order: number }[];
  }>({
    question_id: "",
    question_text: "",
    marks: 1,
    options: [
      { option_text: "", is_correct: true, sort_order: 0 },
      { option_text: "", is_correct: false, sort_order: 1 },
      { option_text: "", is_correct: false, sort_order: 2 },
      { option_text: "", is_correct: false, sort_order: 3 },
    ],
  });

  const editQuestion = (question: ExamQuestion) => {
    setDraft({
      question_id: question.question_id,
      question_text: question.question_text,
      marks: question.marks,
      options:
        question.options.length > 0
          ? question.options.map((option, index) => ({
              option_id: option.option_id,
              option_text: option.option_text,
              is_correct: !!option.is_correct,
              sort_order: index,
            }))
          : [
              { option_text: "", is_correct: true, sort_order: 0 },
              { option_text: "", is_correct: false, sort_order: 1 },
            ],
    });
  };

  const reset = () =>
    setDraft({
      question_id: "",
      question_text: "",
      marks: 1,
      options: [
        { option_text: "", is_correct: true, sort_order: 0 },
        { option_text: "", is_correct: false, sort_order: 1 },
        { option_text: "", is_correct: false, sort_order: 2 },
        { option_text: "", is_correct: false, sort_order: 3 },
      ],
    });

  useEffect(() => {
    reset();
    setValidationError("");
  }, [exam.id]);

  const save = () => {
    const cleanOptions = draft.options
      .map((option, index) => ({ ...option, option_text: option.option_text.trim(), sort_order: index }))
      .filter((option) => option.option_text);
    if (draft.question_text.trim().length < 3) {
      setValidationError("Enter a complete question.");
      return;
    }
    if (cleanOptions.length < 2) {
      setValidationError("Add at least two answer options.");
      return;
    }
    if (!cleanOptions.some((option) => option.is_correct)) {
      setValidationError("Mark one populated option as the correct answer.");
      return;
    }
    setValidationError("");
    saveQuestion.mutate(
      {
        exam_id: exam.id,
        values: {
          ...draft,
          question_type: "mcq",
          status: "active",
          sort_order: questions.data?.length ?? 0,
          options: cleanOptions,
        },
      },
      { onSuccess: reset },
    );
  };

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h4 className="text-sm font-semibold">Question builder</h4>
        <span className="text-xs text-muted-foreground">{questions.data?.length ?? 0} MCQs</span>
      </div>
      <div className="grid gap-3 lg:grid-cols-[1fr_1fr]">
        <div className="space-y-2">
          {(questions.data ?? []).map((question, index) => (
            <div key={question.question_id} className="flex items-stretch gap-2">
              <button
                type="button"
                onClick={() => editQuestion(question)}
                className="min-w-0 flex-1 rounded-lg border border-white/10 bg-white/[0.03] p-3 text-left text-sm transition hover:bg-white/[0.06]"
              >
                <div className="flex items-start justify-between gap-3">
                  <span className="font-medium">{index + 1}. {question.question_text}</span>
                  <span className="shrink-0 rounded-md bg-primary/10 px-2 py-0.5 text-xs text-primary">{question.marks} marks</span>
                </div>
                <div className="mt-1 text-xs text-muted-foreground">
                  {question.options.length} options · {question.options.find((option) => option.is_correct)?.option_text || "No correct option"}
                </div>
              </button>
              <button
                type="button"
                title="Delete question"
                disabled={deleteQuestion.isPending}
                onClick={() => {
                  if (window.confirm("Delete this question and its answer options?")) {
                    deleteQuestion.mutate({ exam_id: exam.id, question_id: question.question_id });
                  }
                }}
                className="grid w-10 place-items-center rounded-lg border border-red-400/20 bg-red-400/5 text-red-200 transition hover:bg-red-400/10 disabled:opacity-50"
              >
                <Trash2 className="h-4 w-4" />
              </button>
            </div>
          ))}
          {!questions.isLoading && !questions.data?.length && (
            <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3 text-sm text-muted-foreground">
              No questions yet. Add MCQs before publishing.
            </div>
          )}
        </div>
        <div className="space-y-2">
          <textarea
            value={draft.question_text}
            onChange={(event) => setDraft((current) => ({ ...current, question_text: event.target.value }))}
            placeholder="Question text"
            rows={3}
            className="w-full rounded-lg border border-white/10 bg-white/5 px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus:border-primary/40"
          />
          <input
            value={draft.marks}
            onChange={(event) => setDraft((current) => ({ ...current, marks: Number(event.target.value) }))}
            type="number"
            min={1}
            className="h-10 w-32 rounded-lg border border-white/10 bg-white/5 px-3 text-sm outline-none focus:border-primary/40"
          />
          {draft.options.map((option, index) => (
            <div key={index} className="flex items-center gap-2">
              <input
                type="radio"
                name={`correct-option-${exam.id}`}
                aria-label={`Mark option ${String.fromCharCode(65 + index)} correct`}
                checked={option.is_correct}
                onChange={() =>
                  setDraft((current) => ({
                    ...current,
                    options: current.options.map((row, idx) => ({ ...row, is_correct: idx === index })),
                  }))
                }
              />
              <input
                value={option.option_text}
                onChange={(event) =>
                  setDraft((current) => ({
                    ...current,
                    options: current.options.map((row, idx) =>
                      idx === index ? { ...row, option_text: event.target.value } : row,
                    ),
                  }))
                }
                placeholder={`Option ${String.fromCharCode(65 + index)}`}
                className="h-10 flex-1 rounded-lg border border-white/10 bg-white/5 px-3 text-sm outline-none placeholder:text-muted-foreground focus:border-primary/40"
              />
            </div>
          ))}
          <div className="flex flex-wrap justify-end gap-2">
            <GlowButton variant="ghost" size="sm" onClick={reset}>New question</GlowButton>
            <GlowButton size="sm" disabled={!draft.question_text.trim() || saveQuestion.isPending} onClick={save}>
              <Plus className="h-4 w-4" />
              {saveQuestion.isPending ? "Saving..." : draft.question_id ? "Update question" : "Add question"}
            </GlowButton>
          </div>
          {(validationError || saveQuestion.error || deleteQuestion.error) && (
            <p className="rounded-lg border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
              {validationError || saveQuestion.error?.message || deleteQuestion.error?.message}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}

function AssignmentPanel({ exam }: { exam: Exam }) {
  const assignments = useExamAssignments(exam.id);
  const assignExam = useAssignExam();
  const revokeAssignment = useRevokeExamAssignment();
  const [studentEmail, setStudentEmail] = useState("");

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h4 className="text-sm font-semibold">Assignments</h4>
        <form
          className="ml-auto flex items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault();
            if (!studentEmail.trim()) return;
            assignExam.mutate(
              { exam_id: exam.id, student_email: studentEmail.trim() },
              { onSuccess: () => setStudentEmail("") },
            );
          }}
        >
            <input
              aria-label="Student email"
              type="email"
              value={studentEmail}
            onChange={(event) => setStudentEmail(event.target.value)}
            placeholder="student@email.edu"
            className="h-9 w-52 rounded-lg border border-white/10 bg-white/5 px-3 text-sm outline-none focus:border-primary/40"
          />
          <GlowButton size="sm" type="submit" disabled={assignExam.isPending || !studentEmail.trim()}>
            <UserPlus className="h-4 w-4" />
            Assign
          </GlowButton>
        </form>
      </div>

      <div className="space-y-2">
        {(assignments.data ?? []).map((row) => (
          <div key={row.assignment_id} className="flex flex-wrap items-center gap-2 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-2">
            <div className="min-w-0 flex-1">
              <div className="truncate text-sm font-medium">{row.student_name}</div>
              <div className="truncate text-xs text-muted-foreground">{row.student_email}</div>
            </div>
            <span className={`rounded-full border px-2 py-0.5 text-xs capitalize ${
              row.status === "revoked"
                ? "border-white/10 bg-white/5 text-muted-foreground"
                : "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
            }`}>
              {row.status}
            </span>
            {row.status !== "revoked" && (
              <button
                type="button"
                title="Revoke assignment"
                onClick={() => revokeAssignment.mutate({ exam_id: exam.id, assignment_id: row.assignment_id })}
                className="inline-grid h-8 w-8 place-items-center rounded-lg border border-white/10 bg-white/5 text-muted-foreground transition hover:text-foreground"
              >
                <X className="h-4 w-4" />
              </button>
            )}
          </div>
        ))}
        {!assignments.isLoading && !assignments.data?.length && (
          <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3 text-sm text-muted-foreground">
            No students assigned yet.
          </div>
        )}
      </div>
      {(assignExam.error || revokeAssignment.error) && (
        <p className="mt-3 rounded-lg border border-destructive/40 bg-destructive/10 p-2 text-xs text-destructive">
          {(assignExam.error || revokeAssignment.error)?.message}
        </p>
      )}
    </div>
  );
}

function AttendancePanel({ exam }: { exam: Exam }) {
  const attendance = useExamAttendance(exam.id);
  const rows = attendance.data ?? [];
  const counts = rows.reduce(
    (acc, row) => {
      const key = row.attempt_status === "submitted" ? "submitted" : row.attempt_status === "in_progress" ? "active" : "not_started";
      acc[key] += 1;
      return acc;
    },
    { not_started: 0, active: 0, submitted: 0 },
  );

  return (
    <div className="rounded-xl border border-white/10 bg-white/[0.03] p-3">
      <div className="mb-3 flex flex-wrap items-center gap-2">
        <h4 className="text-sm font-semibold">Attendance</h4>
        <StatusBadge label={`${counts.not_started} not started`} status="idle" />
        <StatusBadge label={`${counts.active} active`} status="warning" />
        <StatusBadge label={`${counts.submitted} submitted`} status="ok" />
      </div>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[680px] text-sm">
          <thead>
            <tr className="text-left text-[11px] uppercase tracking-wider text-muted-foreground">
              <Th>Student</Th>
              <Th>Roll No.</Th>
              <Th>Status</Th>
              <Th>Score</Th>
              <Th>Risk</Th>
              <Th>Review</Th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row: ExamAttendanceRow) => (
              <tr key={row.assignment_id} className="border-t border-white/5">
                <Td>
                  <div className="font-medium">{row.student_name}</div>
                  <div className="text-[11px] text-muted-foreground">{row.student_email}</div>
                </Td>
                <Td>{row.roll_number || "—"}</Td>
                <Td>
                  <StatusBadge
                    label={row.attempt_status.replace("_", " ")}
                    status={row.attempt_status === "submitted" ? "ok" : row.attempt_status === "in_progress" ? "warning" : "idle"}
                  />
                </Td>
                <Td>{row.score ?? 0}/{row.max_score ?? exam.total_marks ?? 0}</Td>
                <Td>{row.risk_score}</Td>
                <Td>
                  {row.session_id ? (
                    <Link to="/sessions/$sessionId" params={{ sessionId: row.session_id }}>
                      <GlowButton size="sm" variant="ghost">Open</GlowButton>
                    </Link>
                  ) : (
                    <span className="text-xs text-muted-foreground">No session</span>
                  )}
                </Td>
              </tr>
            ))}
          </tbody>
        </table>
        {!attendance.isLoading && rows.length === 0 && (
          <div className="rounded-lg border border-white/10 bg-white/[0.03] p-3 text-sm text-muted-foreground">
            No attendance yet. Assign students to populate this table.
          </div>
        )}
      </div>
    </div>
  );
}

function stringifyRules(rules: unknown) {
  if (!rules || (typeof rules === "object" && Object.keys(rules as Record<string, unknown>).length === 0)) return "";
  return typeof rules === "string" ? rules : JSON.stringify(rules, null, 2);
}

function parseRules(value: string) {
  const trimmed = value.trim();
  if (!trimmed) return {};
  try {
    return JSON.parse(trimmed);
  } catch {
    return trimmed;
  }
}

function toDatetimeLocal(value?: string | null) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 16);
}

function Th({ children }: { children: React.ReactNode }) {
  return <th className="px-4 py-3 font-medium">{children}</th>;
}
function Td({ children }: { children: React.ReactNode }) {
  return <td className="px-4 py-3 align-middle">{children}</td>;
}
