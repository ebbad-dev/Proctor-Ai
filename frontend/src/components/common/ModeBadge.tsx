import { useQuery } from "@tanstack/react-query";
import { Plug, PlugZap } from "lucide-react";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

export function ModeBadge() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: () => api.health(),
    refetchInterval: 30_000,
    retry: false,
  });

  const connected = health.isSuccess && !health.isError;
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px]",
        connected
          ? "border-emerald-400/30 bg-emerald-400/10 text-emerald-200"
          : "border-red-400/30 bg-red-400/10 text-red-200",
      )}
    >
      {connected ? <PlugZap className="h-3 w-3" /> : <Plug className="h-3 w-3" />}
      {connected ? "Live API - Connected" : "Live API - Disconnected"}
    </span>
  );
}
