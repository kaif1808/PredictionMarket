import React from "react";

export function SectionLabel({ children }: { children: React.ReactNode }) {
  return (
    <p className="text-[9px] font-mono uppercase tracking-[0.25em] text-muted-foreground mb-3">
      {children}
    </p>
  );
}
