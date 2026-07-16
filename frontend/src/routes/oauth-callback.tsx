import { createFileRoute, useNavigate } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { redirectForRole, setAuthSession, type AuthSession } from "@/lib/auth";
import { AuthShell } from "./login";

export const Route = createFileRoute("/oauth-callback")({
  head: () => ({ meta: [{ title: "Completing sign in - ProctorAI" }] }),
  component: OAuthCallbackPage,
});

function decodeSession(hash: string): Omit<AuthSession, "logged_in_at"> | null {
  const params = new URLSearchParams(hash.replace(/^#/, ""));
  const encoded = params.get("session");
  if (!encoded) return null;
  try {
    const normalized = encoded.replace(/-/g, "+").replace(/_/g, "/");
    const padded = normalized + "=".repeat((4 - (normalized.length % 4)) % 4);
    return JSON.parse(atob(padded)) as Omit<AuthSession, "logged_in_at">;
  } catch {
    return null;
  }
}

function OAuthCallbackPage() {
  const navigate = useNavigate();
  const [error, setError] = useState("");

  useEffect(() => {
    const session = decodeSession(window.location.hash);
    if (!session?.access_token || !session.user?.role) {
      setError("Google sign-in could not be completed. Please try again.");
      return;
    }
    setAuthSession(session);
    navigate({ to: redirectForRole(session.user.role) });
  }, [navigate]);

  return (
    <AuthShell eyebrow="Google authentication" title="Completing secure sign in">
      <div className="space-y-4">
        {error ? (
          <p className="rounded-xl border border-red-400/30 bg-red-500/10 p-3 text-sm text-red-100">{error}</p>
        ) : (
          <div className="flex items-center gap-3 rounded-2xl border border-white/10 bg-white/[0.06] p-4 text-sm text-cyan-50">
            <Loader2 className="h-4 w-4 animate-spin" />
            Verifying your Google account...
          </div>
        )}
      </div>
    </AuthShell>
  );
}
