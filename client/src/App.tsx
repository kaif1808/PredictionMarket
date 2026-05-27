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
    <div className="container-main">
      <h1 className="mb-2 text-3xl font-semibold">Valdoria Prediction Market</h1>
      <p className="mb-6 text-slate-600">Enter your join token or open the admin console.</p>
      <div className="grid gap-4 md:grid-cols-2">
        <form className="card" onSubmit={joinSession}>
          <h2 className="mb-3 text-lg font-medium">Participant Access</h2>
          <label className="mb-2 block text-sm text-slate-700">Join token</label>
          <input
            className="mb-3 w-full rounded border border-slate-300 px-3 py-2"
            value={joinToken}
            onChange={(e) => setJoinToken(e.target.value)}
            placeholder="e.g. 42:P01"
          />
          <button type="submit" className="btn-primary">
            Join Session
          </button>
          {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
        </form>
        <div className="card">
          <h2 className="mb-3 text-lg font-medium">Admin Access</h2>
          <p className="mb-4 text-sm text-slate-600">
            Use HTTP basic credentials configured on the server.
          </p>
          <Link className="btn-secondary" to="/admin">
            Open Admin Panel
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
