import { createFileRoute, Link } from "@tanstack/react-router";
import { FormEvent, useState } from "react";
import { Mail } from "lucide-react";
import { GlowButton } from "@/components/common/GlowButton";
import { api } from "@/lib/api";
import { AuthShell, Field } from "./login";

export const Route = createFileRoute("/forgot-password")({
  head: () => ({ meta: [{ title: "Forgot password - ProctorAI" }] }),
  component: ForgotPasswordPage,
});

function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  const onSubmit = async (event: FormEvent) => {
    event.preventDefault();
    setError("");
    setMessage("");
    if (!email.includes("@")) {
      setError("Enter your registered email address.");
      return;
    }
    setSubmitting(true);
    try {
      await api.forgotPassword(email);
      setMessage("Password reset email sent. Check your inbox for the secure link.");
    } catch (exc) {
      setError(exc instanceof Error ? exc.message : "Could not send reset email.");
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <AuthShell eyebrow="Secure recovery" title="Reset your password">
      <form className="space-y-4" onSubmit={onSubmit}>
        <Field label="Registered email" value={email} onChange={setEmail} type="email" autoComplete="email" />
        {message && <p className="rounded-xl border border-emerald-400/30 bg-emerald-500/10 p-3 text-sm text-emerald-100">{message}</p>}
        {error && <p className="rounded-xl border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-100">{error}</p>}
        <GlowButton disabled={submitting} className="w-full" size="lg">
          <Mail className="h-4 w-4" />
          {submitting ? "Sending..." : "Send reset link"}
        </GlowButton>
        <Link to="/login" className="block text-sm text-cyan-100/70 hover:text-white">Back to sign in</Link>
      </form>
    </AuthShell>
  );
}
