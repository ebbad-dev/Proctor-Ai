import { createFileRoute } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { AppShell } from "@/components/layout/AppShell";
import { GlassCard } from "@/components/common/GlassCard";
import { GlowButton } from "@/components/common/GlowButton";
import { Switch } from "@/components/ui/switch";
import { Slider } from "@/components/ui/slider";
import type { StrictnessConfig, StrictnessMode } from "@/lib/types";
import { cn } from "@/lib/utils";
import { useSaveSettings, useSettings } from "@/lib/queries";

export const Route = createFileRoute("/settings")({
  head: () => ({
    meta: [
      { title: "Settings · ProctorAI" },
      {
        name: "description",
        content: "Configure strictness, Browser Guard, sensitivities, and risk thresholds.",
      },
    ],
  }),
  component: SettingsPage,
});

function SettingsPage() {
  const [cfg, setCfg] = useState<StrictnessConfig>({
    mode: "high",
    browser_guard_required: true,
    secondary_camera_required: false,
    fullscreen_required: true,
    copy_paste_allowed: false,
    search_engines_allowed: false,
    ai_websites_blocked: true,
    phone_sensitivity: 70,
    gaze_sensitivity: 60,
    audio_sensitivity: 55,
    risk_threshold_medium: 35,
    risk_threshold_high: 60,
    risk_threshold_critical: 80,
  });
  const settings = useSettings();
  const saveSettings = useSaveSettings();

  useEffect(() => {
    const saved = settings.data?.strictness;
    if (saved) setCfg((current) => ({ ...current, ...saved }));
  }, [settings.data]);

  const set = <K extends keyof StrictnessConfig>(k: K, v: StrictnessConfig[K]) =>
    setCfg((c) => ({ ...c, [k]: v }));

  return (
    <AppShell>
      <div className="mx-auto max-w-4xl space-y-4">
        <GlassCard className="flex flex-wrap items-center gap-3 p-4">
          <h1 className="text-lg font-semibold">Strictness & policies</h1>
          <div className="ml-auto flex items-center gap-1 rounded-lg border border-white/10 bg-white/5 p-0.5">
            {(["low", "medium", "high", "custom"] as StrictnessMode[]).map((m) => (
              <button
                key={m}
                onClick={() => set("mode", m)}
                className={cn(
                  "rounded-md px-3 py-1 text-xs capitalize transition-colors",
                  cfg.mode === m
                    ? "bg-gradient-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground",
                )}
              >
                {m}
              </button>
            ))}
          </div>
        </GlassCard>

        <GlassCard className="p-5">
          <h3 className="text-sm font-semibold">Toggles</h3>
          <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-2">
            <Toggle
              label="Browser Guard required"
              value={cfg.browser_guard_required}
              onChange={(v) => set("browser_guard_required", v)}
            />
            <Toggle
              label="Secondary camera required"
              value={cfg.secondary_camera_required}
              onChange={(v) => set("secondary_camera_required", v)}
            />
            <Toggle
              label="Fullscreen required"
              value={cfg.fullscreen_required}
              onChange={(v) => set("fullscreen_required", v)}
            />
            <Toggle
              label="Copy / paste allowed"
              value={cfg.copy_paste_allowed}
              onChange={(v) => set("copy_paste_allowed", v)}
            />
            <Toggle
              label="Search engines allowed"
              value={cfg.search_engines_allowed}
              onChange={(v) => set("search_engines_allowed", v)}
            />
            <Toggle
              label="AI websites blocked"
              value={cfg.ai_websites_blocked}
              onChange={(v) => set("ai_websites_blocked", v)}
            />
          </div>
        </GlassCard>

        <GlassCard className="p-5">
          <h3 className="text-sm font-semibold">Detection sensitivity</h3>
          <div className="mt-4 space-y-5">
            <Range
              label="Phone detection"
              value={cfg.phone_sensitivity}
              onChange={(v) => set("phone_sensitivity", v)}
            />
            <Range
              label="Gaze tracking"
              value={cfg.gaze_sensitivity}
              onChange={(v) => set("gaze_sensitivity", v)}
            />
            <Range
              label="Audio monitoring"
              value={cfg.audio_sensitivity}
              onChange={(v) => set("audio_sensitivity", v)}
            />
          </div>
        </GlassCard>

        <GlassCard className="p-5">
          <h3 className="text-sm font-semibold">Risk thresholds</h3>
          <div className="mt-4 space-y-5">
            <Range
              label="Medium"
              value={cfg.risk_threshold_medium}
              onChange={(v) => set("risk_threshold_medium", v)}
            />
            <Range
              label="High"
              value={cfg.risk_threshold_high}
              onChange={(v) => set("risk_threshold_high", v)}
            />
            <Range
              label="Critical"
              value={cfg.risk_threshold_critical}
              onChange={(v) => set("risk_threshold_critical", v)}
            />
          </div>
        </GlassCard>

        <div className="flex justify-end">
          <GlowButton
            disabled={saveSettings.isPending}
            onClick={() => saveSettings.mutate({ strictness: cfg })}
          >
            {saveSettings.isPending ? "Saving..." : "Save settings"}
          </GlowButton>
        </div>
        {saveSettings.isSuccess && (
          <p className="rounded-xl border border-emerald-400/30 bg-emerald-400/10 p-3 text-sm text-emerald-200">
            Settings saved.
          </p>
        )}
      </div>
    </AppShell>
  );
}

function Toggle({
  label,
  value,
  onChange,
}: {
  label: string;
  value: boolean;
  onChange: (v: boolean) => void;
}) {
  return (
    <label className="flex items-center justify-between rounded-xl border border-white/5 bg-white/[0.03] p-3 text-sm">
      <span>{label}</span>
      <Switch checked={value} onCheckedChange={onChange} />
    </label>
  );
}

function Range({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div>
      <div className="mb-2 flex items-center justify-between text-sm">
        <span>{label}</span>
        <span className="font-mono text-primary">{value}</span>
      </div>
      <Slider value={[value]} onValueChange={(v: number[]) => onChange(v[0]!)} max={100} step={1} />
    </div>
  );
}
