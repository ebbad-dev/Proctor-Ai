import { useEffect, useState } from "react";
import { useNavigate } from "@tanstack/react-router";
import {
  CommandDialog,
  CommandEmpty,
  CommandGroup,
  CommandInput,
  CommandItem,
  CommandList,
  CommandSeparator,
  CommandShortcut,
} from "@/components/ui/command";
import {
  Activity,
  Users,
  FileText,
  Globe,
  Bot,
  Settings,
  ClipboardCheck,
  Camera,
  AlertTriangle,
  SlidersHorizontal,
  ScanFace,
  Search as SearchIcon,
  LogIn,
} from "lucide-react";
import { useDensity } from "@/hooks/use-density";
import { useSessions } from "@/lib/queries";

export function CommandPalette({ trigger }: { trigger?: React.ReactNode }) {
  const [open, setOpen] = useState(false);
  const navigate = useNavigate();
  const { toggle: toggleDensity } = useDensity();
  const sessions = useSessions();
  const latestSessionId = sessions.data?.[0]?.id ?? "";
  const latestSessionDisabled = !latestSessionId;

  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", handler);
    return () => window.removeEventListener("keydown", handler);
  }, []);

  const go = (fn: () => void) => () => {
    setOpen(false);
    fn();
  };

  return (
    <>
      {trigger ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label="Open command palette"
          className="inline-flex items-center gap-2 rounded-lg border border-white/10 bg-white/5 px-2.5 py-1.5 text-xs text-muted-foreground transition hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary/60"
        >
          <SearchIcon className="h-3.5 w-3.5" />
          <span className="hidden sm:inline">Search</span>
          <kbd className="hidden rounded bg-white/10 px-1.5 py-0.5 font-mono text-[10px] text-foreground sm:inline">
            ⌘K
          </kbd>
        </button>
      ) : null}

      <CommandDialog open={open} onOpenChange={setOpen}>
        <CommandInput placeholder="Search pages or run an action…" />
        <CommandList>
          <CommandEmpty>No results found.</CommandEmpty>
          <CommandGroup heading="Navigate">
            <CommandItem onSelect={go(() => navigate({ to: "/login" }))}>
              <LogIn /> Login
            </CommandItem>
            <CommandItem
              onSelect={go(() => navigate({ to: "/monitor", search: { session_id: undefined } }))}
            >
              <Activity /> Live Monitor <CommandShortcut>G M</CommandShortcut>
            </CommandItem>
            <CommandItem
              onSelect={go(() => navigate({ to: "/instructor", search: { risk: undefined } }))}
            >
              <Users /> Instructor Dashboard
            </CommandItem>
            <CommandItem
              disabled={latestSessionDisabled}
              onSelect={go(() =>
                navigate({ to: "/sessions/$sessionId", params: { sessionId: latestSessionId } }),
              )}
            >
              <ClipboardCheck /> Latest Session Review
            </CommandItem>
            <CommandItem
              onSelect={go(() =>
                navigate({
                  to: "/reports",
                  search: { session_id: latestSessionId || undefined },
                }),
              )}
            >
              <FileText /> Reports
            </CommandItem>
            <CommandItem onSelect={go(() => navigate({ to: "/browser-guard" }))}>
              <Globe /> Browser Guard
            </CommandItem>
            <CommandItem onSelect={go(() => navigate({ to: "/assistant" }))}>
              <Bot /> Guide Assistant
            </CommandItem>
            <CommandItem onSelect={go(() => navigate({ to: "/settings" }))}>
              <Settings /> Settings
            </CommandItem>
          </CommandGroup>
          <CommandSeparator />
          <CommandGroup heading="Quick actions">
            <CommandItem
              onSelect={go(() =>
                navigate({ to: "/reports", search: { session_id: latestSessionId || undefined } }),
              )}
            >
              <FileText /> Generate report
            </CommandItem>
            <CommandItem
              disabled={latestSessionDisabled}
              onSelect={go(() =>
                navigate({
                  to: "/sessions/$sessionId",
                  params: { sessionId: latestSessionId },
                  hash: "evidence",
                }),
              )}
            >
              <Camera /> Open latest evidence
            </CommandItem>
            <CommandItem
              onSelect={go(() => navigate({ to: "/instructor", search: { risk: "high" } }))}
            >
              <AlertTriangle /> Filter high-risk sessions
            </CommandItem>
            <CommandItem
              disabled={latestSessionDisabled}
              onSelect={go(() =>
                navigate({
                  to: "/sessions/$sessionId",
                  params: { sessionId: latestSessionId },
                  hash: "browser",
                }),
              )}
            >
              <Globe /> Open browser activity
            </CommandItem>
            <CommandItem onSelect={go(() => navigate({ to: "/settings", hash: "strictness" }))}>
              <SlidersHorizontal /> Switch strictness mode
            </CommandItem>
            <CommandItem onSelect={go(toggleDensity)}>
              <ScanFace /> Toggle density (Comfortable / Compact)
            </CommandItem>
          </CommandGroup>
        </CommandList>
      </CommandDialog>
    </>
  );
}
