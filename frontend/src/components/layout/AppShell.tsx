import { Link, useNavigate, useRouterState } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import {
  ShieldCheck,
  LayoutDashboard,
  Users,
  ClipboardCheck,
  ScanFace,
  DoorOpen,
  FileText,
  Globe,
  Bot,
  Settings,
  Activity,
  Building2,
  ListChecks,
  Rows3,
  Rows4,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { CommandPalette } from "@/components/common/CommandPalette";
import { ModeBadge } from "@/components/common/ModeBadge";
import { EvidenceLightboxProvider } from "@/components/common/EvidenceLightbox";
import { useDensity } from "@/hooks/use-density";
import { clearAuthSession, getAuthSession, redirectForRole, roleCanAccess, type Role } from "@/lib/auth";
import { api } from "@/lib/api";

const nav = [
  { to: "/monitor", label: "Live Monitor", icon: Activity, roles: ["instructor", "admin"] },
  { to: "/instructor", label: "Instructor", icon: Users, roles: ["instructor", "admin"] },
  { to: "/setup", label: "Setup Wizard", icon: ListChecks, roles: ["student", "admin"] },
  { to: "/checklist", label: "Secure Checklist", icon: ClipboardCheck, roles: ["student", "admin"] },
  { to: "/id-verification", label: "ID Verification", icon: ScanFace, roles: ["student", "admin"] },
  { to: "/room-scan", label: "Room Scan", icon: DoorOpen, roles: ["student", "admin"] },
  { to: "/browser-guard", label: "Browser Guard", icon: Globe, roles: ["student", "instructor", "admin"] },
  { to: "/assistant", label: "Guide Assistant", icon: Bot, roles: ["student", "instructor", "admin"] },
  { to: "/reports", label: "Reports", icon: FileText, roles: ["student", "instructor", "admin"] },
  { to: "/admin", label: "Admin Console", icon: Building2, roles: ["admin"] },
  { to: "/settings", label: "Settings", icon: Settings, roles: ["admin"] },
] as const;

export function AppShell({ children }: { children: React.ReactNode }) {
  const navigate = useNavigate();
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const [checked, setChecked] = useState(false);
  const [role, setRole] = useState<Role | undefined>(getAuthSession()?.user.role);

  useEffect(() => {
    const guestRoute = ["/login", "/register", "/forgot-password", "/reset-password"].some(
      (route) => pathname === route,
    );
    if (guestRoute) {
      setChecked(true);
      return;
    }
    const session = getAuthSession();
    if (!session) {
      navigate({ to: "/login" });
      return;
    }
    if (!roleCanAccess(session.user.role, pathname)) {
      navigate({ to: redirectForRole(session.user.role) });
      return;
    }
    setRole(session.user.role);
    api.me().catch(() => {
      clearAuthSession();
      navigate({ to: "/login" });
    });
    setChecked(true);
  }, [navigate, pathname]);

  if (!checked) {
    return (
      <div className="grid min-h-screen place-items-center bg-background text-sm text-muted-foreground">
        Loading ProctorAI...
      </div>
    );
  }

  return (
    <EvidenceLightboxProvider>
      <div className="relative min-h-screen w-full">
        <div aria-hidden className="pointer-events-none fixed inset-0">
          <div className="absolute inset-0 bg-grid opacity-30" />
          <div
            className="absolute -top-32 left-1/3 h-[40rem] w-[40rem] rounded-full blur-3xl"
            style={{ background: "oklch(0.78 0.16 215 / 0.18)" }}
          />
          <div
            className="absolute bottom-0 right-0 h-[36rem] w-[36rem] rounded-full blur-3xl"
            style={{ background: "oklch(0.65 0.22 295 / 0.16)" }}
          />
        </div>

          <div className="relative flex min-h-screen w-full">
          <Sidebar role={role} />
          <div className="flex min-w-0 flex-1 flex-col">
            <TopBar />
            <main className="min-w-0 flex-1 p-4 md:p-6">{children}</main>
          </div>
        </div>
      </div>
    </EvidenceLightboxProvider>
  );
}

function Sidebar({ role }: { role?: Role }) {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const visibleNav = nav.filter((n) => role && (n.roles as readonly Role[]).includes(role));
  return (
    <aside className="sticky top-0 hidden h-screen w-60 shrink-0 border-r border-white/5 bg-background/40 backdrop-blur-xl md:flex md:flex-col">
      <div className="flex items-center gap-2 p-4">
        <div className="grid h-9 w-9 place-items-center rounded-xl bg-gradient-primary shadow-glow">
          <ShieldCheck className="h-5 w-5 text-primary-foreground" aria-hidden />
        </div>
        <div className="leading-tight">
          <div className="font-semibold">ProctorAI</div>
          <div className="text-[10px] uppercase tracking-widest text-muted-foreground">
            Integrity OS
          </div>
        </div>
      </div>
      <nav className="mt-2 flex-1 space-y-1 px-2 pb-4" aria-label="Primary">
        {visibleNav.map((n) => {
          const Icon = n.icon;
          const active = pathname === n.to || pathname.startsWith(n.to + "/");
          return (
            <Link
              key={n.to}
              to={n.to}
              className={cn(
                "group flex items-center gap-3 rounded-xl px-3 py-2 text-sm transition-all focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60",
                active
                  ? "bg-white/10 text-foreground shadow-[inset_0_0_0_1px_oklch(1_0_0_/_0.06)]"
                  : "text-muted-foreground hover:bg-white/5 hover:text-foreground",
              )}
              aria-current={active ? "page" : undefined}
            >
              <Icon
                className={cn("h-4 w-4 transition-colors", active && "text-primary")}
                aria-hidden
              />
              {n.label}
              {active && (
                <span className="ml-auto h-1.5 w-1.5 rounded-full bg-primary shadow-[0_0_8px_2px_oklch(0.78_0.16_215_/_0.7)]" />
              )}
            </Link>
          );
        })}
      </nav>
      <div className="mx-3 mb-3 rounded-xl border border-white/10 bg-white/5 p-3 text-xs text-muted-foreground">
        <div className="mb-1 font-medium text-foreground">Mode</div>
        <ModeBadge />
        <div className="mt-2 text-[11px]">
          Press <kbd className="rounded bg-white/10 px-1">⌘K</kbd> to open the command palette.
        </div>
      </div>
    </aside>
  );
}

function TopBar() {
  const pathname = useRouterState({ select: (s) => s.location.pathname });
  const current = nav.find((n) => pathname === n.to || pathname.startsWith(n.to + "/"));
  const { density, toggle } = useDensity();
  const navigate = useNavigate();
  return (
    <header className="sticky top-0 z-20 flex h-14 items-center gap-3 border-b border-white/5 bg-background/40 px-4 backdrop-blur-xl md:px-6">
      <Link
        to="/"
        className="md:hidden focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60 rounded-lg"
        aria-label="ProctorAI home"
      >
        <div className="grid h-8 w-8 place-items-center rounded-lg bg-gradient-primary">
          <ShieldCheck className="h-4 w-4 text-primary-foreground" aria-hidden />
        </div>
      </Link>
      <div className="flex items-center gap-2 text-sm text-muted-foreground">
        <LayoutDashboard className="h-4 w-4" aria-hidden />
        <span className="text-foreground">{current?.label ?? "Overview"}</span>
      </div>
      <div className="ml-auto flex items-center gap-2">
        <ModeBadge />
        <CommandPalette trigger />
        <button
          type="button"
          onClick={toggle}
          aria-label={`Switch to ${density === "comfortable" ? "compact" : "comfortable"} density`}
          title={`Density: ${density}`}
          className="inline-grid h-9 w-9 place-items-center rounded-lg border border-white/10 bg-white/5 text-muted-foreground transition hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
        >
          {density === "compact" ? (
            <Rows4 className="h-4 w-4" aria-hidden />
          ) : (
            <Rows3 className="h-4 w-4" aria-hidden />
          )}
        </button>
        <button
          type="button"
          onClick={() => {
            api.logout();
            navigate({ to: "/login" });
          }}
          className="h-8 rounded-lg border border-white/10 bg-white/5 px-3 text-xs text-muted-foreground transition hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
        >
          Logout
        </button>
      </div>
    </header>
  );
}
