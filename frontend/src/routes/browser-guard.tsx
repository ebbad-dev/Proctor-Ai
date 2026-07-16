import { createFileRoute } from "@tanstack/react-router";
import { useState } from "react";
import { motion } from "framer-motion";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/common/GlassCard";
import { GlowButton } from "@/components/common/GlowButton";
import { StatusBadge } from "@/components/common/StatusBadge";
import { ParticleField } from "@/components/effects/ParticleField";
import { api } from "@/lib/api";
import { useBrowserGuardActive } from "@/lib/queries";
import { Chrome, FolderOpen, ShieldCheck, ShieldOff, Wifi, Zap } from "lucide-react";

export const Route = createFileRoute("/browser-guard")({
  head: () => ({
    meta: [
      { title: "Browser Guard Setup · ProctorAI" },
      {
        name: "description",
        content:
          "Install and verify the ProctorAI Browser Guard extension for exact tab and URL tracking.",
      },
    ],
  }),
  component: BrowserGuardPage,
});

function BrowserGuardPage() {
  const [testing, setTesting] = useState(false);
  const [testError, setTestError] = useState(false);
  const guard = useBrowserGuardActive();
  const active = !!guard.data?.active;

  const testConnection = async () => {
    setTesting(true);
    setTestError(false);
    try {
      await api.pingBrowserGuard();
      await guard.refetch();
    } catch {
      setTestError(true);
    } finally {
      setTesting(false);
    }
  };

  return (
    <AppShell>
      <div className="space-y-4">
        <GlassCard className="relative overflow-hidden p-6 md:p-8">
          <ParticleField count={30} />
          <div className="relative grid grid-cols-1 gap-6 md:grid-cols-[1fr_auto] md:items-center">
            <div>
              <div className="text-xs uppercase tracking-widest text-muted-foreground">
                Browser extension
              </div>
              <h1 className="mt-1 text-3xl font-bold">
                Browser <span className="text-gradient">Guard</span>
              </h1>
              <p className="mt-2 max-w-xl text-sm text-muted-foreground">
                Browser Guard enables exact tab and URL tracking during active exam sessions.
                Without it, ProctorAI can only detect basic tab-switch events.
              </p>
              <div className="mt-4 flex items-center gap-2">
                <StatusBadge
                  label={active ? "Active" : "Inactive"}
                  status={active ? "ok" : "warning"}
                  pulse={active}
                />
                <StatusBadge
                  label={
                    guard.isError ? "Backend unreachable" : testing ? "Testing" : "Live status"
                  }
                  status={guard.isError ? "error" : testing ? "info" : "info"}
                />
              </div>
            </div>
            <ShieldVisual active={active} />
          </div>
        </GlassCard>

        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <GlassCard className="p-5 lg:col-span-2">
            <h3 className="text-sm font-semibold">Install instructions</h3>
            <ol className="mt-3 space-y-3 text-sm">
              {[
                {
                  t: "Load the extension folder",
                  d: "Open chrome://extensions or edge://extensions and choose Load unpacked.",
                  icon: FolderOpen,
                },
                {
                  t: "Select Browser Guard",
                  d: "Choose the browser_guard_extension folder inside this ProctorAI project.",
                  icon: Chrome,
                },
                {
                  t: "Grant required permissions",
                  d: "Allow tab/URL access for exam sessions only.",
                  icon: ShieldCheck,
                },
                { t: "Test connection", d: "Verify ProctorAI receives the handshake.", icon: Zap },
              ].map((step, i) => (
                <motion.li
                  key={step.t}
                  initial={{ opacity: 0, x: -8 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ delay: i * 0.07 }}
                  className="flex items-start gap-3 rounded-xl border border-white/5 bg-white/[0.03] p-3"
                >
                  <div className="grid h-9 w-9 place-items-center rounded-lg bg-primary/15 text-primary">
                    <step.icon className="h-4 w-4" />
                  </div>
                  <div>
                    <div className="font-medium">
                      {i + 1}. {step.t}
                    </div>
                    <div className="text-xs text-muted-foreground">{step.d}</div>
                  </div>
                </motion.li>
              ))}
            </ol>

            <div className="mt-4 flex flex-wrap items-center gap-2">
              <GlowButton variant="outline" onClick={testConnection} disabled={testing}>
                <Wifi className="h-4 w-4" /> {testing ? "Testing..." : "Test connection"}
              </GlowButton>
            </div>
            {testError && (
              <p className="mt-3 rounded-lg border border-red-400/30 bg-red-400/10 p-3 text-xs text-red-200">
                Browser Guard ping failed. Start the FastAPI backend and confirm the extension is
                allowed to call localhost.
              </p>
            )}
          </GlassCard>

          <GlassCard className="p-5">
            <h3 className="text-sm font-semibold">Privacy</h3>
            <p className="mt-2 text-sm text-muted-foreground">
              Browser Guard monitors browser activity only during active exam sessions. It does not
              collect unrelated browsing history.
            </p>
            <div className="mt-3 space-y-2 text-xs">
              <Row label="Scope" value="Active exam sessions only" />
              <Row label="Data stored" value="Domain, tab title, timestamps" />
              <Row label="Retention" value="Aligned with exam record" />
            </div>
          </GlassCard>
        </div>
      </div>
    </AppShell>
  );
}

function Row({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between rounded-lg border border-white/5 bg-white/[0.03] px-3 py-2">
      <span className="text-muted-foreground">{label}</span>
      <span>{value}</span>
    </div>
  );
}

function ShieldVisual({ active }: { active: boolean }) {
  return (
    <div className="relative grid h-44 w-44 place-items-center">
      <div
        className={`absolute inset-0 rounded-full blur-2xl ${active ? "" : "opacity-30"}`}
        style={{ background: "var(--gradient-glow)" }}
      />
      <div
        className={`relative grid h-32 w-32 place-items-center rounded-3xl glass-strong ${active ? "shadow-glow animate-pulse-glow" : ""}`}
      >
        {active ? (
          <ShieldCheck className="h-12 w-12 text-primary" />
        ) : (
          <ShieldOff className="h-12 w-12 text-muted-foreground" />
        )}
      </div>
    </div>
  );
}
