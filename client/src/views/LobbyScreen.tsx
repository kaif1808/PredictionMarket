import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet } from "../lib/api";
import type { ParticipantState } from "../types/events";
import { Radio } from "lucide-react";

export default function LobbyScreen() {
  const navigate = useNavigate();
  const [state, setState] = useState<ParticipantState | null>(null);
  const [dots, setDots] = useState(".");

  // Animated dots
  useEffect(() => {
    const t = setInterval(() => setDots((d) => (d.length >= 3 ? "." : d + ".")), 700);
    return () => clearInterval(t);
  }, []);

  // Polling loop — preserved exactly
  useEffect(() => {
    let active = true;
    async function refresh() {
      try {
        const s = (await apiGet("/state")) as ParticipantState;
        if (!active) return;
        setState(s);
        if (s.phase === "round_open" || s.phase === "market_open") {
          navigate("/trade");
        }
        if (s.flow_step === "debrief") {
          navigate("/debrief");
        }
      } catch {
        setState(null);
      }
    }
    refresh();
    const t = setInterval(refresh, 2000);
    return () => {
      active = false;
      clearInterval(t);
    };
  }, [navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center px-6">
      <div className="w-full max-w-xs">
        <div className="border border-border bg-card/60 p-8">
          <div className="flex items-center gap-2.5 mb-8">
            <Radio className="w-4 h-4 text-muted-foreground/50 animate-pulse" />
            <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground/50">
              Awaiting session start
            </span>
          </div>
          <h1
            className="text-2xl font-light leading-snug mb-1"
            style={{ fontFamily: "Spectral, Georgia, serif" }}
          >
            Waiting for session{dots}
          </h1>
          <p className="text-xs text-muted-foreground/50 font-mono mb-7">
            The experimenter will open the market shortly.
          </p>

          {state && (
            <div className="space-y-2.5 mb-8 border-t border-b border-border py-4">
              {[
                ["Session", String(state.session_id ?? "—")],
                ["Phase", state.phase ?? "—"],
                ["Flow step", state.flow_step ?? "—"],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="text-[11px] font-mono text-muted-foreground/50">{k}</span>
                  <span className={`text-[11px] font-mono ${k === "Phase" ? "text-amber-400/80" : "text-foreground/70"}`}>
                    {v}
                  </span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
