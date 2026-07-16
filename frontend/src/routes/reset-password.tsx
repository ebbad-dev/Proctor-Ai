import { createFileRoute, Link } from "@tanstack/react-router";
import { FormEvent, useState } from "react";
import { KeyRound } from "lucide-react";
import { GlowButton } from "@/components/common/GlowButton";
import { api } from "@/lib/api";
import { AuthShell, Field } from "./login";

export const Route = createFileRoute("/reset-password")({
  validateSearch: (search: Record<string, unknown>) => ({ token: search.token as string | undefined }),
  head: () => ({ meta: [{ title: "Reset password - ProctorAI" }] }),
  component: ResetPasswordPage,
});

function ResetPasswordPage() {
  const { token } = Route.useSearch();
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!token) {
      setError("Reset token is missing.");
      return;
    }
    if (password !== confirm || password.length < 8) {
      setError("Passwords must match and be at least 8 characters.");
      return;
    }
    setSubmitting(true);
    try {
      await api.resetPassword(token, password);
      setMessage("Password updated. You can now sign in with the new password.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not reset password.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell eyebrow="One-time reset link" title="Choose a new password">
      <form className="space-y-4" onSubmit={onSubmit}>
        <Field label="New password" value={password} onChange={setPassword} type="password" autoComplete="new-password" />
        <Field label="Confirm password" value={confirm} onChange={setConfirm} type="password" autoComplete="new-password" />
        {message && <p className="rounded-xl border border-emerald-400/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">{message}</p>}
        {error && <p className="rounded-xl border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-100">{error}</p>}
        <GlowButton disabled={submitting} className="w-full" size="lg">
          <KeyRound className="h-4 w-4" />
          {submitting ? "Saving..." : "Update password"}
        </GlowButton>
        <Link to="/login" className="block text-sm text-cyan-100/70 hover:text-white">Back to sign in</Link>
      </form>
    </AuthShell>
  );
}
