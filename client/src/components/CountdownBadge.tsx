import { Clock } from "lucide-react";

interface CountdownBadgeProps {
  seconds: number | null;
}

export function CountdownBadge({ seconds }: CountdownBadgeProps) {
  if (seconds === null) {
    return (
      <div className="flex items-center gap-1.5 px-3 py-1 border border-muted-foreground/20 font-mono text-[11px] text-muted-foreground/50">
        <Clock className="w-3 h-3" />
        —
      </div>
    );
  }
  const closed = seconds === 0;
  const urgent = !closed && seconds < 15;
  return (
    <div
      className={`flex items-center gap-1.5 px-3 py-1 border font-mono text-[11px] tabular-nums tracking-wide ${
        closed
          ? "border-red-500/25 bg-red-500/8 text-red-400/70"
          : urgent
          ? "border-amber-500/25 bg-amber-500/8 text-amber-400/80"
          : "border-border text-muted-foreground/60"
      }`}
    >
      <Clock className="w-3 h-3" />
      {closed ? "CLOSED" : `0:${String(seconds).padStart(2, "0")}`}
    </div>
  );
}
