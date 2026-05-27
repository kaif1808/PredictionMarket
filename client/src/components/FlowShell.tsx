import React from "react";

interface FlowShellProps {
  step: number;
  total: number;
  title: string;
  children: React.ReactNode;
}

export function FlowShell({ step, total, title, children }: FlowShellProps) {
  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6 py-16">
      <div className="w-full max-w-lg">
        {/* Progress bar */}
        <div className="flex items-center gap-3 mb-8">
          <div className="flex gap-1">
            {Array.from({ length: total }).map((_, i) => (
              <div
                key={i}
                className={`h-0.5 w-6 rounded-full transition-colors ${
                  i < step ? "bg-foreground" : "bg-border"
                }`}
              />
            ))}
          </div>
          <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-[0.15em]">
            {step} / {total}
          </span>
        </div>
        {/* Title */}
        <h1
          className="text-2xl font-light leading-snug mb-8 text-foreground"
          style={{ fontFamily: "Spectral, Georgia, serif" }}
        >
          {title}
        </h1>
        {children}
      </div>
    </div>
  );
}
