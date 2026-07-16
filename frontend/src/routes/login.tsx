import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { FormEvent, useState } from "react";
import {
  Activity,
  ArrowRight,
  Eye,
  EyeOff,
  Fingerprint,
  LockKeyhole,
  Radar,
  ShieldCheck,
  Sparkles,
} from "lucide-react";
import { AnimatedShield } from "@/components/effects/AnimatedShield";
import { GlowButton } from "@/components/common/GlowButton";
import { API_BASE_URL, endpoints } from "@/config/endpoints";
import { api } from "@/lib/api";
import { redirectForRole } from "@/lib/auth";

export const Route = createFileRoute("/login")({
  head: () => ({
    meta: [
      { title: "Sign in - ProctorAI" },
      {
        name: "description",
        content: "Secure AI-powered exam monitoring login for students and instructors.",
      },
    ],
  }),
  component: LoginPage,
});

function LoginPage() {
  const navigate = useNavigate();
  const oauthError =
    typeof window === "undefined"
      ? ""
      : new URLSearchParams(window.location.search).get("oauth_error") || "";
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (!email.includes("@") || password.length < 1) {
      setError("Enter your email and password.");
      return;
    }
    setSubmitting(true);
    try {
      const session = await api.login(email, password);
      navigate({ to: redirectForRole(session.user.role) });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Unable to sign in.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell eyebrow="Secure AI-Powered Exam Monitoring" title="Welcome back">
      <form className="space-y-4" onSubmit={onSubmit}>
        <Field label="Email address" type="email" value={email} onChange={setEmail} autoComplete="email" />
        <label className="block text-sm">
          <span className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-cyan-100/70">
            Password
          </span>
          <div className="group flex h-12 items-center rounded-2xl border border-white/10 bg-white/[0.065] px-3 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] transition duration-300 focus-within:border-cyan-200/70 focus-within:bg-white/[0.09] focus-within:shadow-[0_0_0_3px_rgba(34,211,238,0.14),inset_0_1px_0_rgba(255,255,255,0.12)]">
            <input
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              type={show ? "text" : "password"}
              autoComplete="current-password"
              className="min-w-0 flex-1 bg-transparent text-sm text-white outline-none placeholder:text-white/35"
              placeholder="Enter your password"
            />
            <button
              type="button"
              onClick={() => setShow((v) => !v)}
              className="grid h-8 w-8 place-items-center rounded-lg text-white/60 transition hover:bg-white/10 hover:text-white"
              aria-label={show ? "Hide password" : "Show password"}
            >
              {show ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
            </button>
          </div>
        </label>

        {(error || oauthError) && (
          <p className="rounded-xl border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-100">
            {error || oauthError}
          </p>
        )}

        <GoogleAuthButton label="Continue with Google" />

        <div className="flex items-center gap-3 text-xs uppercase tracking-[0.22em] text-cyan-100/45">
          <span className="h-px flex-1 bg-white/10" />
          <span>Email access</span>
          <span className="h-px flex-1 bg-white/10" />
        </div>

        <GlowButton disabled={submitting} className="w-full" size="lg">
          <LockKeyhole className="h-4 w-4" />
          {submitting ? "Verifying..." : "Sign in securely"}
          {!submitting && <ArrowRight className="h-4 w-4" />}
        </GlowButton>

        <div className="flex flex-wrap items-center justify-between gap-2 text-sm text-cyan-100/70">
          <Link to="/forgot-password" className="transition hover:text-white">
            Forgot password?
          </Link>
          <span>
            New student?{" "}
            <Link to="/register" className="font-medium text-cyan-200 transition hover:text-white">
              Create account
            </Link>
          </span>
        </div>
      </form>
    </AuthShell>
  );
}

export function GoogleAuthButton({ label = "Continue with Google" }: { label?: string }) {
  const onClick = () => {
    window.location.assign(`${API_BASE_URL}${endpoints.googleStart}`);
  };

  return (
    <button
      type="button"
      onClick={onClick}
      className="group flex h-12 w-full items-center justify-center gap-3 rounded-2xl border border-white/12 bg-white/[0.07] px-4 text-sm font-medium text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.10)] transition duration-300 hover:-translate-y-0.5 hover:border-cyan-100/35 hover:bg-white/[0.10] hover:shadow-[0_20px_60px_-35px_rgba(34,211,238,0.75)]"
    >
      <span className="grid h-7 w-7 place-items-center rounded-full bg-white text-sm font-bold text-slate-950 transition duration-300 group-hover:scale-105">
        G
      </span>
      {label}
    </button>
  );
}

export function AuthShell({
  eyebrow,
  title,
  children,
}: {
  eyebrow: string;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <main className="relative min-h-screen overflow-hidden bg-[#020611] text-white">
      <div className="absolute inset-0 bg-[radial-gradient(ellipse_at_18%_8%,rgba(34,211,238,0.24),transparent_38%),radial-gradient(ellipse_at_86%_18%,rgba(124,58,237,0.22),transparent_34%),linear-gradient(135deg,#020611_0%,#06101d_46%,#0b1026_100%)]" />
      <div className="absolute inset-0 bg-[linear-gradient(rgba(255,255,255,0.038)_1px,transparent_1px),linear-gradient(90deg,rgba(255,255,255,0.038)_1px,transparent_1px)] bg-[size:52px_52px] [mask-image:linear-gradient(to_bottom,rgba(0,0,0,0.82),transparent_92%)]" />
      <div className="absolute left-0 top-0 h-px w-full bg-gradient-to-r from-transparent via-cyan-200/60 to-transparent" />
      <div className="absolute inset-x-0 top-16 h-64 bg-[linear-gradient(90deg,transparent,rgba(34,211,238,0.10),transparent)] blur-3xl" />

      <section className="relative mx-auto grid min-h-screen max-w-7xl grid-cols-1 items-center gap-10 px-5 py-8 sm:px-8 lg:grid-cols-[minmax(0,1fr)_460px] lg:px-10">
        <div className="max-w-3xl py-8">
          <div className="mb-9 flex items-center gap-3">
            <div className="grid h-12 w-12 place-items-center rounded-2xl bg-cyan-300 text-slate-950 shadow-[0_0_42px_rgba(34,211,238,0.5)] transition duration-500 hover:scale-105 hover:rotate-3">
              <ShieldCheck className="h-6 w-6" />
            </div>
            <div>
              <div className="text-xl font-semibold tracking-tight">ProctorAI</div>
              <div className="text-xs uppercase tracking-[0.28em] text-cyan-100/60">Integrity Intelligence</div>
            </div>
          </div>

          <div className="inline-flex items-center gap-2 rounded-full border border-cyan-200/15 bg-cyan-200/10 px-3 py-1 text-xs text-cyan-100 shadow-[0_0_28px_rgba(34,211,238,0.12)] backdrop-blur">
            <Sparkles className="h-3.5 w-3.5" />
            {eyebrow}
          </div>

          <h1 className="mt-5 max-w-3xl text-4xl font-bold leading-tight md:text-6xl">
            Secure AI exam monitoring for high-trust institutions.
          </h1>

          <p className="mt-5 max-w-2xl text-base leading-7 text-slate-300">
            Real-time monitoring, smart alerts, secure exam sessions, evidence-backed reviews, and role-based access for serious academic environments.
          </p>

          <div className="mt-9 grid max-w-2xl grid-cols-1 gap-3 sm:grid-cols-3">
            {[
              { icon: Radar, label: "Live detection", value: "Camera, audio, browser" },
              { icon: Activity, label: "Risk scoring", value: "Event-backed analysis" },
              { icon: Fingerprint, label: "Access control", value: "Student, instructor, admin" },
            ].map((item) => (
              <div
                key={item.label}
                className="group rounded-2xl border border-white/10 bg-white/[0.045] p-4 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] backdrop-blur transition duration-300 hover:-translate-y-1 hover:border-cyan-200/35 hover:bg-white/[0.075] hover:shadow-[0_20px_60px_-34px_rgba(34,211,238,0.65)]"
              >
                <item.icon className="h-5 w-5 text-cyan-200 transition duration-300 group-hover:scale-110" />
                <div className="mt-3 text-sm font-medium">{item.label}</div>
                <div className="mt-1 text-xs leading-5 text-slate-400">{item.value}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="relative mx-auto w-full max-w-[460px]">
          <div className="pointer-events-none absolute -inset-[1px] rounded-[2rem] bg-[linear-gradient(135deg,rgba(103,232,249,0.55),rgba(168,85,247,0.22),rgba(20,184,166,0.28))] opacity-70 blur-[1px]" />
          <div className="group relative overflow-hidden rounded-[2rem] border border-white/15 bg-white/[0.075] p-6 shadow-[0_30px_100px_-38px_rgba(34,211,238,0.72),inset_0_1px_0_rgba(255,255,255,0.20)] backdrop-blur-2xl transition duration-500 hover:-translate-y-1 hover:border-cyan-100/35 hover:bg-white/[0.095] hover:shadow-[0_42px_120px_-42px_rgba(34,211,238,0.82),inset_0_1px_0_rgba(255,255,255,0.26)]">
            <div className="pointer-events-none absolute inset-x-0 top-0 h-28 bg-[linear-gradient(110deg,transparent,rgba(255,255,255,0.22),transparent)] opacity-0 blur-xl transition duration-700 group-hover:translate-x-16 group-hover:opacity-100" />
            <div className="pointer-events-none absolute inset-x-8 top-0 h-px bg-gradient-to-r from-transparent via-white/55 to-transparent" />
            <div className="pointer-events-none absolute inset-y-8 right-0 w-px bg-gradient-to-b from-transparent via-cyan-100/30 to-transparent" />

            <div className="relative mb-6 flex items-start justify-between gap-5">
              <div>
                <div className="text-xs uppercase tracking-[0.24em] text-cyan-100/60">Secure access</div>
                <h2 className="mt-2 text-3xl font-semibold">{title}</h2>
                <p className="mt-2 text-sm leading-6 text-slate-300">Use your registered ProctorAI account.</p>
              </div>
              <div className="hidden shrink-0 sm:block">
                <AnimatedShield size={86} />
              </div>
            </div>

            <div className="relative">
              {children}
            </div>

            <div className="relative mt-6 grid grid-cols-3 gap-2 rounded-2xl border border-white/10 bg-slate-950/35 p-2 text-center text-[11px] text-cyan-100/70 shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
              <span>Encrypted auth</span>
              <span>RBAC enforced</span>
              <span>Audit logged</span>
            </div>
          </div>
        </div>
      </section>
    </main>
  );
}

export function Field({
  label,
  value,
  onChange,
  type = "text",
  autoComplete,
  placeholder,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  type?: string;
  autoComplete?: string;
  placeholder?: string;
}) {
  return (
    <label className="block text-sm">
      <span className="mb-1.5 block text-xs font-medium uppercase tracking-wider text-cyan-100/70">
        {label}
      </span>
      <input
        value={value}
        onChange={(event) => onChange(event.target.value)}
        type={type}
        autoComplete={autoComplete}
        placeholder={placeholder}
        className="h-12 w-full rounded-2xl border border-white/10 bg-white/[0.065] px-3 text-sm text-white shadow-[inset_0_1px_0_rgba(255,255,255,0.08)] outline-none transition duration-300 placeholder:text-white/35 hover:bg-white/[0.08] focus:border-cyan-200/70 focus:bg-white/[0.09] focus:shadow-[0_0_0_3px_rgba(34,211,238,0.14),inset_0_1px_0_rgba(255,255,255,0.12)]"
      />
    </label>
  );
}
