import { createFileRoute, Link, useNavigate } from "@tanstack/react-router";
import { FormEvent, useState } from "react";
import { UserPlus } from "lucide-react";
import { GlowButton } from "@/components/common/GlowButton";
import { api } from "@/lib/api";
import { redirectForRole } from "@/lib/auth";
import { AuthShell, Field, GoogleAuthButton } from "./login";

export const Route = createFileRoute("/register")({
  head: () => ({ meta: [{ title: "Create student account - ProctorAI" }] }),
  component: RegisterPage,
});

function RegisterPage() {
  const navigate = useNavigate();
  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    if (fullName.trim().length < 2 || !email.includes("@") || password.length < 8) {
      setError("Enter a valid name, email, and password of at least 8 characters.");
      return;
    }
    setSubmitting(true);
    try {
      const session = await api.register({ full_name: fullName.trim(), email, password });
      navigate({ to: redirectForRole(session.user.role) });
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not create account.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell eyebrow="Student registration" title="Create your ProctorAI account">
      <form className="space-y-4" onSubmit={onSubmit}>
        <Field label="Full name" value={fullName} onChange={setFullName} autoComplete="name" />
        <Field label="Email address" value={email} onChange={setEmail} type="email" autoComplete="email" />
        <Field label="Password" value={password} onChange={setPassword} type="password" autoComplete="new-password" placeholder="8+ chars, upper/lowercase, number" />
        {error && <p className="rounded-xl border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-100">{error}</p>}
        <GoogleAuthButton label="Sign up with Google" />
        <div className="flex items-center gap-3 text-xs uppercase tracking-[0.22em] text-cyan-100/45">
          <span className="h-px flex-1 bg-white/10" />
          <span>Email signup</span>
          <span className="h-px flex-1 bg-white/10" />
        </div>
        <GlowButton disabled={submitting} className="w-full" size="lg">
          <UserPlus className="h-4 w-4" />
          {submitting ? "Creating..." : "Create student account"}
        </GlowButton>
        <p className="text-sm text-cyan-100/70">
          Already registered? <Link to="/login" className="font-medium text-cyan-200 hover:text-white">Sign in</Link>
        </p>
      </form>
    </AuthShell>
  );
}
