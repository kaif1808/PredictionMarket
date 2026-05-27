import { Link, useNavigate } from "react-router-dom";
import { useEffect, useState } from "react";
import { apiGet } from "../lib/api";
import type { ParticipantState } from "../types/events";

export default function LobbyScreen() {
  const navigate = useNavigate();
  const [state, setState] = useState<ParticipantState | null>(null);

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
    <div className="container-main">
      <div className="card">
        <h1 className="mb-2 text-2xl font-semibold">Lobby</h1>
        <p className="text-slate-700">
          Waiting for the admin to start your market. This page auto-refreshes.
        </p>
        {state ? (
          <div className="mt-4 text-sm text-slate-600">
            <p>Session: {state.session_id}</p>
            <p>Phase: {state.phase}</p>
            <p>Flow step: {state.flow_step}</p>
          </div>
        ) : null}
        <div className="mt-5">
          <Link className="btn-secondary" to="/">
            Return Home
          </Link>
        </div>
      </div>
    </div>
  );
}
