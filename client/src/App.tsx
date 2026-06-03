import { Link, Navigate, Route, Routes, useNavigate } from "react-router-dom";
import { useState } from "react";
import { apiPost } from "./lib/api";
import TradingView from "./views/TradingView";
import AdminPanel from "./views/AdminPanel";
import ConsentScreen from "./views/aux/ConsentScreen";
import InstructionsScreen from "./views/aux/InstructionsScreen";
import ComprehensionQuizScreen from "./views/aux/ComprehensionQuizScreen";
import HoltLauryScreen from "./views/aux/HoltLauryScreen";
import DebriefScreen from "./views/aux/DebriefScreen";
import LobbyScreen from "./views/LobbyScreen";

function Home() {
  const navigate = useNavigate();
  const [joinToken, setJoinToken] = useState("");
  const [error, setError] = useState("");

  async function joinSession(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setError("");
    try {
      await apiPost("/auth/join", { join_token: joinToken });
      navigate("/consent");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Join failed");
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6 py-20">
      {/* Wordmark */}
      <div className="mb-14 text-center">
        <p className="text-[10px] font-mono uppercase tracking-[0.3em] text-muted-foreground/40 mb-5">
          Experimental Economics · Prediction Markets
        </p>
        <h1
          className="text-5xl font-light tracking-tight leading-[1.1] mb-4"
          style={{ fontFamily: "Spectral, Georgia, serif" }}
        >
          Valdoria
          <span className="text-muted-foreground/40 mx-3 font-extralight">·</span>
          Prediction Market
        </h1>
        <div className="w-12 h-px bg-border mx-auto" />
      </div>

      <div className="w-full max-w-md space-y-3">
        <form onSubmit={joinSession} className="border border-border bg-card/60 p-6">
          <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground/50 mb-5">
            Participant Access
          </p>
          <label className="block text-xs font-mono text-muted-foreground/70 mb-2 tracking-wide">
            Join token
          </label>
          <input
            value={joinToken}
            onChange={(e) => { setJoinToken(e.target.value); setError(""); }}
            placeholder="e.g. 42:P01"
            className="w-full bg-transparent border-b border-border px-0 py-2 text-sm font-mono mb-6 focus:outline-none focus:border-foreground/50 placeholder:text-muted-foreground/25 transition-colors"
          />
          <button
            type="submit"
            className="w-full py-3 bg-foreground text-background text-xs font-mono uppercase tracking-[0.15em] hover:opacity-90 transition-opacity"
          >
            Enter Session
          </button>
          {error && <p className="mt-3 text-xs text-red-400 font-mono">{error}</p>}
        </form>

        <div className="border border-border/50 bg-card/30 px-6 py-4 flex items-center justify-between">
          <div>
            <p className="text-[10px] font-mono uppercase tracking-[0.2em] text-muted-foreground/40 mb-0.5">
              Experimenter Access
            </p>
            <p className="text-xs font-mono text-muted-foreground/50">Admin console via HTTP basic auth</p>
          </div>
          <Link
            to="/admin"
            className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground hover:text-foreground transition-colors border border-border px-3 py-1.5"
          >
            Admin →
          </Link>
        </div>
      </div>
    </div>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/consent" element={<ConsentScreen />} />
      <Route path="/instructions" element={<InstructionsScreen />} />
      <Route path="/quiz" element={<ComprehensionQuizScreen />} />
      <Route path="/risk" element={<HoltLauryScreen />} />
      <Route path="/lobby" element={<LobbyScreen />} />
      <Route path="/trade" element={<TradingView />} />
      <Route path="/debrief" element={<DebriefScreen />} />
      <Route path="/admin" element={<AdminPanel />} />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}
