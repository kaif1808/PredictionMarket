import { useEffect, useMemo, useState } from "react";
import { apiPost } from "../lib/api";

type AdminAuth = { user: string; pass: string };
type SessionRow = { session_id: number; label: string; rotation_id: number; closed_at: string | null };
type ParticipantRow = { participant_id: string; flow_step: string; joined_at: string };
type TournamentRow = {
  participant_id: string;
  rank: number;
  total_tokens: number;
  prize_eur?: number;
  paid_at?: string | null;
  provisional?: boolean;
  markets_completed?: number;
};
type DashboardMarket = {
  market_id: number;
  market_number: number;
  stage: number;
  scenario_id: string;
  current_price: number;
  total_volume: number;
  rounds_opened: number;
  latest_round_number: number | null;
  latest_closing_price: number | null;
  latest_benchmark: number | null;
};
type DashboardResponse = {
  session_id: number;
  label: string;
  phase: string;
  current_market_number: number | null;
  current_round_number: number | null;
  participant_count: number;
  markets: DashboardMarket[];
};

async function authedGet<T>(path: string, auth: AdminAuth): Promise<T> {
  const res = await fetch(path, {
    headers: { Authorization: `Basic ${btoa(`${auth.user}:${auth.pass}`)}` }
  });
  if (!res.ok) {
    throw new Error(await res.text());
  }
  const type = res.headers.get("content-type") || "";
  if (type.includes("application/json")) return (await res.json()) as T;
  return (await res.text()) as T;
}

export default function AdminPanel() {
  const [auth, setAuth] = useState<AdminAuth>({ user: "admin", pass: "admin" });
  const [sessions, setSessions] = useState<SessionRow[]>([]);
  const [selectedSession, setSelectedSession] = useState<number | null>(null);
  const [participants, setParticipants] = useState<ParticipantRow[]>([]);
  const [tournamentRows, setTournamentRows] = useState<TournamentRow[]>([]);
  const [dashboard, setDashboard] = useState<DashboardResponse | null>(null);
  const [message, setMessage] = useState("");
  const [exportText, setExportText] = useState("");
  const [marketNumber, setMarketNumber] = useState(1);
  const [roundNumber, setRoundNumber] = useState(1);

  async function loadSessions() {
    const rows = await authedGet<SessionRow[]>("/admin/sessions", auth);
    setSessions(rows);
    if (!selectedSession && rows.length > 0) {
      setSelectedSession(rows[0].session_id);
    }
  }

  async function loadParticipants() {
    if (!selectedSession) return;
    const rows = await authedGet<ParticipantRow[]>(`/admin/sessions/${selectedSession}/participants`, auth);
    setParticipants(rows);
  }

  async function loadTournament() {
    if (!selectedSession) return;
    try {
      const rows = await authedGet<TournamentRow[]>(`/admin/sessions/${selectedSession}/tournament`, auth);
      setTournamentRows(rows);
    } catch {
      try {
        const provisional = await authedGet<TournamentRow[]>(
          `/admin/sessions/${selectedSession}/tournament/provisional`,
          auth
        );
        setTournamentRows(provisional);
      } catch {
        setTournamentRows([]);
      }
    }
  }

  async function loadDashboard() {
    if (!selectedSession) return;
    try {
      const payload = await authedGet<DashboardResponse>(`/admin/sessions/${selectedSession}/dashboard`, auth);
      setDashboard(payload);
    } catch {
      setDashboard(null);
    }
  }

  useEffect(() => {
    loadSessions().catch((err) => setMessage(err instanceof Error ? err.message : "Load failed"));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    loadParticipants().catch(() => {});
    loadTournament().catch(() => {});
    loadDashboard().catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSession]);

  async function createSession() {
    const label = `S${new Date().toISOString().slice(0, 10)}-A`;
    const created = (await apiPost(
      "/admin/sessions",
      { label, rotation_id: 1, subject_count: 16 },
      auth
    )) as { session_id: number };
    setSelectedSession(created.session_id);
    await loadSessions();
    await loadParticipants();
    await loadTournament();
    await loadDashboard();
    setMessage(`Session ${created.session_id} created.`);
  }

  async function action(path: string, body: unknown = {}) {
    if (!selectedSession) return;
    await apiPost(path.replace("{sid}", String(selectedSession)), body, auth);
    await loadSessions();
    await loadParticipants();
    await loadTournament();
    await loadDashboard();
    setMessage(`Action completed: ${path}`);
  }

  async function fetchExport(kind: "csv" | "json") {
    if (!selectedSession) return;
    const data = await authedGet<string | object>(`/admin/sessions/${selectedSession}/export.${kind}`, auth);
    setExportText(typeof data === "string" ? data : JSON.stringify(data, null, 2));
  }

  async function markPaid(participantId: string) {
    if (!selectedSession) return;
    await apiPost(
      `/admin/sessions/${selectedSession}/tournament/mark_paid`,
      { participant_id: participantId },
      auth
    );
    await loadTournament();
  }

  async function emergencyAction(kind: "round" | "market" | "session") {
    if (!selectedSession) return;
    const reason = window.prompt("Emergency override reason (required for audit log):");
    if (!reason || !reason.trim()) {
      setMessage("Emergency action cancelled: reason is required.");
      return;
    }
    const pathByKind = {
      round: `/admin/sessions/${selectedSession}/emergency/round_close`,
      market: `/admin/sessions/${selectedSession}/emergency/market_resolve`,
      session: `/admin/sessions/${selectedSession}/emergency/session_close`
    };
    await apiPost(pathByKind[kind], { reason }, auth);
    await loadSessions();
    await loadParticipants();
    await loadTournament();
    await loadDashboard();
    setMessage(`Emergency action completed: ${kind}`);
  }

  const selected = useMemo(
    () => sessions.find((s) => s.session_id === selectedSession) || null,
    [sessions, selectedSession]
  );

  return (
    <div className="container-main space-y-4">
      <div className="card">
        <h1 className="mb-3 text-2xl font-semibold">Admin Panel</h1>
        <div className="mb-2 flex flex-wrap gap-2">
          <input
            className="rounded border border-slate-300 px-2 py-1 text-sm"
            value={auth.user}
            onChange={(e) => setAuth((a) => ({ ...a, user: e.target.value }))}
            placeholder="admin user"
          />
          <input
            className="rounded border border-slate-300 px-2 py-1 text-sm"
            type="password"
            value={auth.pass}
            onChange={(e) => setAuth((a) => ({ ...a, pass: e.target.value }))}
            placeholder="admin pass"
          />
          <button className="btn-secondary" onClick={() => loadSessions().catch((err) => setMessage(err instanceof Error ? err.message : "Refresh failed"))}>
            Refresh
          </button>
          <button className="btn-primary" onClick={() => createSession().catch((err) => setMessage(err instanceof Error ? err.message : "Create failed"))}>
            Start New Session
          </button>
        </div>
        {message ? <p className="text-sm text-slate-700">{message}</p> : null}
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        <div className="card">
          <h2 className="mb-2 text-lg font-medium">Sessions</h2>
          <div className="space-y-2 text-sm">
            {sessions.map((s) => (
              <button
                key={s.session_id}
                className={`block w-full rounded border px-3 py-2 text-left ${
                  selectedSession === s.session_id ? "border-cyan-600 bg-cyan-50" : "border-slate-200"
                }`}
                onClick={() => setSelectedSession(s.session_id)}
              >
                #{s.session_id} • {s.label} • rotation {s.rotation_id}
                <br />
                <span className="text-xs text-slate-500">
                  {s.closed_at ? `Closed at ${s.closed_at}` : "Active"}
                </span>
              </button>
            ))}
          </div>
        </div>

        <div className="card">
          <h2 className="mb-2 text-lg font-medium">Session Control</h2>
          {selected ? (
            <div className="space-y-2">
              <p className="text-sm text-slate-600">Selected session: {selected.session_id}</p>
              <div className="flex flex-wrap items-center gap-3 text-sm">
                <label>
                  Market
                  <select
                    className="ml-2 rounded border border-slate-300 px-2 py-1"
                    value={marketNumber}
                    onChange={(e) => setMarketNumber(Number(e.target.value))}
                  >
                    {[1, 2, 3, 4].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>
                <label>
                  Round
                  <select
                    className="ml-2 rounded border border-slate-300 px-2 py-1"
                    value={roundNumber}
                    onChange={(e) => setRoundNumber(Number(e.target.value))}
                  >
                    {[1, 2, 3, 4, 5].map((n) => (
                      <option key={n} value={n}>
                        {n}
                      </option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="flex flex-wrap gap-2">
                <button
                  className="btn-secondary"
                  onClick={() =>
                    action("/admin/sessions/{sid}/markets", { market_number: marketNumber }).catch((err) =>
                      setMessage(err instanceof Error ? err.message : "Action failed")
                    )
                  }
                >
                  Start Market {marketNumber}
                </button>
                <button
                  className="btn-primary"
                  onClick={() =>
                    action("/admin/sessions/{sid}/rounds", { round_number: roundNumber }).catch((err) =>
                      setMessage(err instanceof Error ? err.message : "Action failed")
                    )
                  }
                >
                  Start Round {roundNumber}
                </button>
                <button
                  className="btn-secondary"
                  onClick={() =>
                    action(`/admin/sessions/${selectedSession}/rounds/${roundNumber}/end`).catch((err) =>
                      setMessage(err instanceof Error ? err.message : "Action failed")
                    )
                  }
                >
                  End Round {roundNumber}
                </button>
                <button
                  className="btn-secondary"
                  onClick={() =>
                    action(`/admin/sessions/${selectedSession}/markets/${marketNumber}/resolve`).catch((err) =>
                      setMessage(err instanceof Error ? err.message : "Action failed")
                    )
                  }
                >
                  Resolve Market {marketNumber}
                </button>
              </div>
              <button className="btn-danger" onClick={() => action("/admin/sessions/{sid}/close").catch((err) => setMessage(err instanceof Error ? err.message : "Action failed"))}>
                Close Session
              </button>
              <div className="mt-2 flex flex-wrap gap-2">
                <button
                  className="btn-danger"
                  onClick={() => emergencyAction("round").catch((err) => setMessage(err instanceof Error ? err.message : "Action failed"))}
                >
                  Emergency Round Close
                </button>
                <button
                  className="btn-danger"
                  onClick={() => emergencyAction("market").catch((err) => setMessage(err instanceof Error ? err.message : "Action failed"))}
                >
                  Emergency Market Resolve
                </button>
                <button
                  className="btn-danger"
                  onClick={() => emergencyAction("session").catch((err) => setMessage(err instanceof Error ? err.message : "Action failed"))}
                >
                  Emergency Session Close
                </button>
              </div>
            </div>
          ) : (
            <p className="text-sm text-slate-600">No session selected.</p>
          )}
        </div>
      </div>

      <div className="card">
        <h2 className="mb-2 text-lg font-medium">Participant Phase Control</h2>
        <div className="space-y-2 text-sm">
          {participants.map((p) => (
            <div key={p.participant_id} className="flex flex-wrap items-center gap-2 rounded border border-slate-200 p-2">
              <span className="w-24 font-medium">{p.participant_id}</span>
              <span className="w-32">{p.flow_step}</span>
              <button
                className="btn-secondary"
                onClick={() =>
                  apiPost(
                    `/admin/sessions/${selectedSession}/participants/${p.participant_id}/flow`,
                    { flow_step: "lobby" },
                    auth
                  )
                    .then(() => loadParticipants())
                    .catch((err) => setMessage(err instanceof Error ? err.message : "Action failed"))
                }
              >
                Force Lobby
              </button>
              <button
                className="btn-secondary"
                onClick={() =>
                  apiPost(
                    `/admin/sessions/${selectedSession}/participants/${p.participant_id}/flow`,
                    { flow_step: "debrief" },
                    auth
                  )
                    .then(() => loadParticipants())
                    .catch((err) => setMessage(err instanceof Error ? err.message : "Action failed"))
                }
              >
                Force Debrief
              </button>
            </div>
          ))}
        </div>
      </div>

      <div className="card">
        <h2 className="mb-2 text-lg font-medium">Live Monitor</h2>
        <div className="mb-3 flex gap-2">
          <button className="btn-secondary" onClick={() => loadDashboard().catch((err) => setMessage(err instanceof Error ? err.message : "Load failed"))}>
            Refresh Monitor
          </button>
        </div>
        {!dashboard ? (
          <p className="text-sm text-slate-600">No dashboard data yet.</p>
        ) : (
          <div className="space-y-2 text-sm">
            <p>
              Phase: <span className="font-medium">{dashboard.phase}</span> • Current market:{" "}
              {dashboard.current_market_number ?? "-"} • Current round: {dashboard.current_round_number ?? "-"}
            </p>
            {dashboard.markets.map((m) => (
              <div key={m.market_id} className="rounded border border-slate-200 p-2">
                <p className="font-medium">
                  Market {m.market_number} (Stage {m.stage}, Scenario {m.scenario_id})
                </p>
                <p>
                  Price: {(Number(m.current_price) * 100).toFixed(1)}% • Volume: {m.total_volume} • Rounds:{" "}
                  {m.rounds_opened}
                </p>
                <p>
                  Latest round: {m.latest_round_number ?? "-"} • Close:{" "}
                  {m.latest_closing_price == null ? "-" : Number(m.latest_closing_price).toFixed(3)} • Benchmark:{" "}
                  {m.latest_benchmark == null ? "-" : Number(m.latest_benchmark).toFixed(3)}
                </p>
              </div>
            ))}
          </div>
        )}
      </div>

      <div className="card">
        <h2 className="mb-2 text-lg font-medium">Tournament</h2>
        <div className="mb-3 flex gap-2">
          <button className="btn-secondary" onClick={() => loadTournament().catch((err) => setMessage(err instanceof Error ? err.message : "Load failed"))}>
            Refresh Tournament
          </button>
        </div>
        <div className="space-y-2 text-sm">
          {tournamentRows.length === 0 ? (
            <p className="text-slate-600">No tournament computed yet.</p>
          ) : (
            tournamentRows.map((r) => (
              <div key={r.participant_id} className="flex flex-wrap items-center gap-2 rounded border border-slate-200 p-2">
                <span className="w-20 font-medium">{r.participant_id}</span>
                <span className="w-16">Rank {r.rank}</span>
                <span className="w-32">{Number(r.total_tokens).toFixed(2)} tokens</span>
                <span className="w-20">
                  {r.provisional ? "-" : `€${Number(r.prize_eur || 0).toFixed(2)}`}
                </span>
                <span className="w-44 text-xs text-slate-500">
                  {r.provisional ? `provisional (${r.markets_completed ?? 0} markets)` : (r.paid_at || "unpaid")}
                </span>
                {!r.provisional ? (
                  <button className="btn-secondary" onClick={() => markPaid(r.participant_id).catch((err) => setMessage(err instanceof Error ? err.message : "Action failed"))}>
                    Mark Paid
                  </button>
                ) : null}
              </div>
            ))
          )}
        </div>
      </div>

      <div className="card">
        <h2 className="mb-2 text-lg font-medium">Exports</h2>
        <div className="mb-3 flex gap-2">
          <button className="btn-secondary" onClick={() => fetchExport("csv").catch((err) => setMessage(err instanceof Error ? err.message : "Load failed"))}>
            Load CSV
          </button>
          <button className="btn-secondary" onClick={() => fetchExport("json").catch((err) => setMessage(err instanceof Error ? err.message : "Load failed"))}>
            Load JSON
          </button>
        </div>
        <pre className="max-h-72 overflow-auto rounded bg-slate-900 p-3 text-xs text-slate-100">
          {exportText || "No export loaded yet."}
        </pre>
      </div>
    </div>
  );
}
