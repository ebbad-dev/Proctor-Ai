import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import type { RiskScore } from "@/lib/types";

interface Props {
  data: RiskScore["trend"];
}

export function RiskTrendChart({ data }: Props) {
  const chartData = data.map((d) => ({
    time: new Date(d.t).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }),
    score: d.score,
  }));
  return (
    <div className="h-40 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <AreaChart data={chartData} margin={{ top: 6, right: 6, bottom: 0, left: 0 }}>
          <defs>
            <linearGradient id="riskA" x1="0" y1="0" x2="0" y2="1">
              <stop offset="0%" stopColor="oklch(0.78 0.16 215)" stopOpacity={0.6} />
              <stop offset="100%" stopColor="oklch(0.78 0.16 215)" stopOpacity={0} />
            </linearGradient>
          </defs>
          <XAxis dataKey="time" hide />
          <YAxis hide domain={[0, 100]} />
          <Tooltip
            contentStyle={{
              background: "oklch(0.2 0.03 260 / 0.9)",
              border: "1px solid oklch(1 0 0 / 0.1)",
              borderRadius: 12,
              color: "white",
              fontSize: 12,
            }}
          />
          <Area
            type="monotone"
            dataKey="score"
            stroke="oklch(0.82 0.15 200)"
            strokeWidth={2}
            fill="url(#riskA)"
          />
        </AreaChart>
      </ResponsiveContainer>
    </div>
  );
}
