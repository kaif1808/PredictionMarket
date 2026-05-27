import { useEffect, useMemo, useState } from "react";
import { apiPost } from "../lib/api";
import { SectionLabel } from "../components/SectionLabel";
import {
  RefreshCw, Users, BarChart2, Award, Download, AlertOctagon,
} from "lucide-react";

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
type AdminTab = "control" | "participants" | "monitor" | "tournament" | "exports";

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
  const [tab, setTab] = useState<AdminTab>("control");

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

  async function verifyLogin() {
    try {
      await loadSessions();
      await loadParticipants();
      await loadTournament();
      await loadDashboard();
      setMessage("Admin credentials verified.");
    } catch (err) {
      setSessions([]);
      setParticipants([]);
      setTournamentRows([]);
      setDashboard(null);
      setMessage(err instanceof Error ? err.message : "Invalid admin credentials");
    }
  }

  const selected = useMemo(
    () => sessions.find((s) => s.session_id === selectedSession) || null,
    [sessions, selectedSession]
  );

  const tabs: { id: AdminTab; label: string; icon: React.ReactNode }[] = [
    { id: "control",      label: "Session Control", icon: <RefreshCw className="w-3.5 h-3.5" /> },
    { id: "participants", label: "Participants",     icon: <Users className="w-3.5 h-3.5" /> },
    { id: "monitor",      label: "Live Monitor",    icon: <BarChart2 className="w-3.5 h-3.5" /> },
    { id: "tournament",   label: "Tournament",      icon: <Award className="w-3.5 h-3.5" /> },
    { id: "exports",      label: "Exports",         icon: <Download className="w-3.5 h-3.5" /> },
  ];

  return (
    <div className="min-h-screen flex flex-col">
      {/* Admin header */}
      <header className="border-b border-border shrink-0">
        <div className="max-w-6xl mx-auto px-5 h-12 flex items-center justify-between">
          <div className="flex items-center gap-3">
            <span className="text-[10px] font-mono uppercase tracking-[0.25em] text-muted-foreground">
              Experimenter Console
            </span>
            {selected && (
              <>
                <span className="text-border">·</span>
                <span className="text-[11px] font-mono text-foreground/70">{selected.label}</span>
                <span className={`inline-flex items-center gap-1.5 ml-1 px-2 py-0.5 border ${selected.closed_at ? "border-border text-muted-foreground" : "border-green-500/25 bg-green-500/8"}`}>
                  {!selected.closed_at && <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />}
                  <span className={`text-[9px] font-mono uppercase tracking-[0.15em] ${selected.closed_at ? "text-muted-foreground" : "text-green-400"}`}>
                    {selected.closed_at ? "Closed" : "Active"}
                  </span>
                </span>
              </>
            )}
          </div>
          <div className="flex items-center gap-3">
            <input
              className="bg-transparent border border-border px-2 py-1 text-[11px] font-mono focus:outline-none focus:border-foreground/40 w-24"
              value={auth.user}
              onChange={(e) => setAuth((a) => ({ ...a, user: e.target.value }))}
              placeholder="user"
            />
            <input
              className="bg-transparent border border-border px-2 py-1 text-[11px] font-mono focus:outline-none focus:border-foreground/40 w-24"
              type="password"
              value={auth.pass}
              onChange={(e) => setAuth((a) => ({ ...a, pass: e.target.value }))}
              onKeyDown={(e) => {
                if (e.key === "Enter") {
                  e.preventDefault();
                  verifyLogin().catch(() => {});
                }
              }}
              placeholder="pass"
            />
            <button
              onClick={() => verifyLogin().catch(() => {})}
              className="px-3 py-1 border border-border text-[10px] font-mono uppercase tracking-[0.12em] text-foreground hover:bg-foreground/5 transition-colors"
            >
              Verify Login
            </button>
          </div>
        </div>
      </header>

      {/* Tabs */}
      <div className="border-b border-border shrink-0">
        <div className="max-w-6xl mx-auto px-5 flex">
          {tabs.map((t) => (
            <button
              key={t.id}
              onClick={() => setTab(t.id)}
              className={`flex items-center gap-1.5 px-4 py-3 text-[11px] font-mono uppercase tracking-[0.1em] border-b-2 transition-colors ${
                tab === t.id
                  ? "border-foreground text-foreground"
                  : "border-transparent text-muted-foreground hover:text-foreground"
              }`}
            >
              {t.icon}
              {t.label}
            </button>
          ))}
        </div>
      </div>

      <div className="flex-1 max-w-6xl mx-auto w-full px-5 py-6">
        {/* Feedback bar */}
        {message && (
          <div className="mb-4 px-4 py-2.5 border border-green-500/25 bg-green-500/5 text-[11px] font-mono text-green-400 flex items-center justify-between">
            <span>{message}</span>
            <button onClick={() => setMessage("")} className="text-muted-foreground hover:text-foreground ml-4">×</button>
          </div>
        )}

        {/* ── SESSION CONTROL ── */}
        {tab === "control" && (
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
              <SectionLabel>Sessions</SectionLabel>
              <div className="space-y-1 mb-4">
                {sessions.map((s) => (
                  <button
                    key={s.session_id}
                    onClick={() => setSelectedSession(s.session_id)}
                    className={`block w-full text-left border px-4 py-3 transition-colors ${
                      selectedSession === s.session_id
                        ? "border-foreground/40 bg-foreground/5"
                        : "border-border hover:border-foreground/20"
                    }`}
                  >
                    <p className="text-[11px] font-mono text-foreground">#{s.session_id} · {s.label}</p>
                    <p className="text-[10px] font-mono text-muted-foreground mt-0.5">
                      {s.closed_at ? `Closed ${s.closed_at.slice(0, 10)}` : "Active"} · rotation {s.rotation_id}
                    </p>
                  </button>
                ))}
              </div>
              <div className="space-y-2">
                <button
                  onClick={() => createSession().catch((err) => setMessage(err instanceof Error ? err.message : "Create failed"))}
                  className="w-full py-2.5 border border-border text-[11px] font-mono uppercase tracking-[0.1em] text-foreground hover:bg-foreground/5 transition-colors"
                >
                  + Create New Session
                </button>
                <button
                  onClick={() => action("/admin/sessions/{sid}/close").catch((err) => setMessage(err instanceof Error ? err.message : "Action failed"))}
                  className="w-full py-2.5 border border-red-500/25 bg-red-500/5 text-[11px] font-mono uppercase tracking-[0.1em] text-red-500 hover:bg-red-500/10 transition-colors"
                >
                  Close Session
                </button>
              </div>
            </div>

            <div className="space-y-6">
              {selected ? (
                <>
                  <div>
                    <SectionLabel>Market & Round Control</SectionLabel>
                    <div className="border border-border p-4 space-y-4">
                      <div className="flex gap-4">
                        <div className="flex-1">
                          <label className="block text-[9px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-1.5">Market</label>
                          <select
                            value={marketNumber}
                            onChange={(e) => setMarketNumber(Number(e.target.value))}
                            className="w-full bg-background border border-border px-3 py-2 text-sm font-mono focus:outline-none"
                          >
                            {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n}</option>)}
                          </select>
                        </div>
                        <div className="flex-1">
                          <label className="block text-[9px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-1.5">Round</label>
                          <select
                            value={roundNumber}
                            onChange={(e) => setRoundNumber(Number(e.target.value))}
                            className="w-full bg-background border border-border px-3 py-2 text-sm font-mono focus:outline-none"
                          >
                            {[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
                          </select>
                        </div>
                      </div>
                      <div className="grid grid-cols-2 gap-2">
                        <button
                          onClick={() => action("/admin/sessions/{sid}/markets", { market_number: marketNumber }).catch((err) => setMessage(err instanceof Error ? err.message : "Action failed"))}
                          className="py-2.5 border border-border text-[10px] font-mono uppercase tracking-[0.1em] text-foreground hover:bg-foreground/5 transition-colors"
                        >
                          Start Market {marketNumber}
                        </button>
                        <button
                          onClick={() => action("/admin/sessions/{sid}/rounds", { round_number: roundNumber }).catch((err) => setMessage(err instanceof Error ? err.message : "Action failed"))}
                          className="py-2.5 bg-foreground text-background text-[10px] font-mono uppercase tracking-[0.1em] hover:opacity-90 transition-opacity"
                        >
                          Start Round {roundNumber}
                        </button>
                        <button
                          onClick={() => action(`/admin/sessions/${selectedSession}/rounds/${roundNumber}/end`).catch((err) => setMessage(err instanceof Error ? err.message : "Action failed"))}
                          className="py-2.5 border border-border text-[10px] font-mono uppercase tracking-[0.1em] text-foreground hover:bg-foreground/5 transition-colors"
                        >
                          End Round {roundNumber}
                        </button>
                        <button
                          onClick={() => action(`/admin/sessions/${selectedSession}/markets/${marketNumber}/resolve`).catch((err) => setMessage(err instanceof Error ? err.message : "Action failed"))}
                          className="py-2.5 border border-border text-[10px] font-mono uppercase tracking-[0.1em] text-foreground hover:bg-foreground/5 transition-colors"
                        >
                          Resolve Market {marketNumber}
                        </button>
                      </div>
                    </div>
                  </div>

                  <div>
                    <SectionLabel>Emergency Overrides</SectionLabel>
                    <div className="border border-red-500/20 bg-red-500/3 p-4 space-y-2">
                      <p className="text-[10px] font-mono text-red-500/70 mb-3">All overrides require a reason and are audit-logged.</p>
                      {(["round", "market", "session"] as const).map((kind) => (
                        <button
                          key={kind}
                          onClick={() => emergencyAction(kind).catch((err) => setMessage(err instanceof Error ? err.message : "Action failed"))}
                          className="w-full py-2 flex items-center gap-2 border border-red-500/25 text-[10px] font-mono uppercase tracking-[0.1em] text-red-500 hover:bg-red-500/8 transition-colors px-3"
                        >
                          <AlertOctagon className="w-3 h-3 shrink-0" />
                          Emergency {kind === "round" ? "Round Close" : kind === "market" ? "Market Resolve" : "Session Close"}
                        </button>
                      ))}
                    </div>
                  </div>
                </>
              ) : (
                <p className="text-sm font-mono text-muted-foreground">Select a session to manage it.</p>
              )}
            </div>
          </div>
        )}

        {/* ── PARTICIPANTS ── */}
        {tab === "participants" && (
          <div>
            <div className="flex items-center justify-between mb-4">
              <SectionLabel>Participant Status</SectionLabel>
              <button
                onClick={() => loadParticipants().catch((err) => setMessage(err instanceof Error ? err.message : "Load failed"))}
                className="flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground hover:text-foreground transition-colors uppercase tracking-[0.1em]"
              >
                <RefreshCw className="w-3 h-3" /> Refresh
              </button>
            </div>
            <div className="border border-border overflow-hidden">
              <div className="grid grid-cols-[6rem_1fr_6rem_6rem] border-b border-border bg-card/60">
                {["ID", "Flow Step", "Joined", "Actions"].map((h) => (
                  <div key={h} className="px-4 py-2 text-[9px] font-mono uppercase tracking-[0.12em] text-muted-foreground border-r border-border last:border-r-0">
                    {h}
                  </div>
                ))}
              </div>
              {participants.length === 0 ? (
                <div className="px-4 py-6 text-sm font-mono text-muted-foreground">No participants yet.</div>
              ) : participants.map((p) => (
                <div key={p.participant_id} className="grid grid-cols-[6rem_1fr_6rem_6rem] border-b border-border last:border-b-0">
                  <div className="px-4 py-2.5 text-[11px] font-mono text-foreground border-r border-border">{p.participant_id}</div>
                  <div className="px-4 py-2.5 text-[11px] font-mono text-muted-foreground border-r border-border">{p.flow_step}</div>
                  <div className="px-4 py-2.5 text-[10px] font-mono text-muted-foreground border-r border-border">
                    {p.joined_at ? new Date(p.joined_at).toLocaleTimeString() : "—"}
                  </div>
                  <div className="px-3 py-1.5 flex items-center gap-1">
                    <button
                      onClick={() => apiPost(`/admin/sessions/${selectedSession}/participants/${p.participant_id}/flow`, { flow_step: "lobby" }, auth).then(() => loadParticipants()).catch((err) => setMessage(err instanceof Error ? err.message : "Action failed"))}
                      className="px-2 py-1 text-[9px] font-mono uppercase tracking-[0.08em] border border-border text-muted-foreground hover:text-foreground hover:border-foreground/40 transition-colors"
                    >
                      Lobby
                    </button>
                    <button
                      onClick={() => apiPost(`/admin/sessions/${selectedSession}/participants/${p.participant_id}/flow`, { flow_step: "debrief" }, auth).then(() => loadParticipants()).catch((err) => setMessage(err instanceof Error ? err.message : "Action failed"))}
                      className="px-2 py-1 text-[9px] font-mono uppercase tracking-[0.08em] border border-border text-muted-foreground hover:text-foreground hover:border-foreground/40 transition-colors"
                    >
                      Debrief
                    </button>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── LIVE MONITOR ── */}
        {tab === "monitor" && (
          <div className="space-y-6">
            <div className="flex items-center justify-between">
              <SectionLabel>Market Overview</SectionLabel>
              <button
                onClick={() => loadDashboard().catch((err) => setMessage(err instanceof Error ? err.message : "Load failed"))}
                className="flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground hover:text-foreground transition-colors uppercase tracking-[0.1em]"
              >
                <RefreshCw className="w-3 h-3" /> Refresh
              </button>
            </div>
            {!dashboard ? (
              <p className="text-sm font-mono text-muted-foreground">No dashboard data yet. Select a session and refresh.</p>
            ) : (
              <>
                <div className="text-[11px] font-mono text-muted-foreground">
                  Phase: <span className="text-foreground">{dashboard.phase}</span>
                  {dashboard.current_market_number != null && (
                    <span> · Market {dashboard.current_market_number} · Round {dashboard.current_round_number ?? "—"}</span>
                  )}
                  <span> · {dashboard.participant_count} participants</span>
                </div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {dashboard.markets.map((m) => (
                    <div key={m.market_id} className="border border-border p-5">
                      <div className="mb-4">
                        <span className="text-[9px] font-mono uppercase tracking-[0.2em] text-muted-foreground">
                          Market {m.market_number} · Stage {m.stage} · Scenario {m.scenario_id}
                        </span>
                      </div>
                      <div className="flex items-baseline gap-2 mb-3">
                        <span className="text-3xl font-mono font-semibold tabular-nums">
                          {(Number(m.current_price) * 100).toFixed(1)}%
                        </span>
                        <span className="text-xs font-mono text-muted-foreground">P(YES)</span>
                      </div>
                      <div className="grid grid-cols-3 gap-3">
                        {[
                          ["Volume", `${m.total_volume} contracts`],
                          ["Rounds", `${m.rounds_opened} / 5`],
                          ["Benchmark", m.latest_benchmark != null ? (Number(m.latest_benchmark) * 100).toFixed(1) + "%" : "—"],
                        ].map(([k, v]) => (
                          <div key={k}>
                            <p className="text-[9px] font-mono uppercase tracking-[0.12em] text-muted-foreground mb-1">{k}</p>
                            <p className="text-[11px] font-mono text-foreground">{v}</p>
                          </div>
                        ))}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            )}
          </div>
        )}

        {/* ── TOURNAMENT ── */}
        {tab === "tournament" && (
          <div className="space-y-4">
            <div className="flex items-center justify-between">
              <SectionLabel>Tournament Standings</SectionLabel>
              <div className="flex items-center gap-3">
                <span className="text-[10px] font-mono text-amber-400/70 uppercase tracking-[0.1em]">
                  {tournamentRows.some((r) => r.provisional) ? "Provisional" : "Final"}
                </span>
                <button
                  onClick={() => loadTournament().catch((err) => setMessage(err instanceof Error ? err.message : "Load failed"))}
                  className="flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground hover:text-foreground transition-colors uppercase tracking-[0.1em]"
                >
                  <RefreshCw className="w-3 h-3" /> Refresh
                </button>
              </div>
            </div>
            {tournamentRows.length === 0 ? (
              <p className="text-sm font-mono text-muted-foreground">No tournament data yet.</p>
            ) : (
              <div className="border border-border overflow-hidden">
                <div className="grid grid-cols-[3rem_5rem_1fr_6rem_5rem_6rem] border-b border-border bg-card/60">
                  {["Rank", "ID", "Status", "Tokens", "Prize", "Actions"].map((h) => (
                    <div key={h} className="px-4 py-2 text-[9px] font-mono uppercase tracking-[0.12em] text-muted-foreground border-r border-border last:border-r-0">
                      {h}
                    </div>
                  ))}
                </div>
                {tournamentRows.map((r) => (
                  <div key={r.participant_id} className={`grid grid-cols-[3rem_5rem_1fr_6rem_5rem_6rem] border-b border-border last:border-b-0 ${r.rank === 1 ? "bg-amber-500/3" : ""}`}>
                    <div className="px-4 py-3 flex items-center border-r border-border">
                      {r.rank <= 3 ? (
                        <Award className={`w-3.5 h-3.5 ${r.rank === 1 ? "text-amber-400" : r.rank === 2 ? "text-slate-400" : "text-amber-700/70"}`} />
                      ) : (
                        <span className="text-[11px] font-mono tabular-nums text-muted-foreground">{r.rank}</span>
                      )}
                    </div>
                    <div className="px-4 py-3 text-[11px] font-mono text-foreground border-r border-border">{r.participant_id}</div>
                    <div className="px-4 py-3 text-[10px] font-mono text-muted-foreground border-r border-border">
                      {r.provisional ? `provisional (${r.markets_completed ?? 0} markets)` : (r.paid_at ? `paid ${r.paid_at.slice(0, 10)}` : "unpaid")}
                    </div>
                    <div className="px-4 py-3 text-[11px] font-mono tabular-nums text-foreground border-r border-border">
                      {Number(r.total_tokens).toFixed(1)} T
                    </div>
                    <div className={`px-4 py-3 text-[11px] font-mono tabular-nums border-r border-border ${(r.prize_eur || 0) > 0 ? "text-green-500" : "text-muted-foreground"}`}>
                      {(r.prize_eur || 0) > 0 ? `€${Number(r.prize_eur).toFixed(2)}` : "—"}
                    </div>
                    <div className="px-3 py-2 flex items-center">
                      {!r.provisional && (r.prize_eur || 0) > 0 && (
                        <button
                          onClick={() => markPaid(r.participant_id).catch((err) => setMessage(err instanceof Error ? err.message : "Action failed"))}
                          className="px-2 py-1 text-[9px] font-mono uppercase tracking-[0.08em] border border-border text-muted-foreground hover:text-foreground hover:border-foreground/40 transition-colors"
                        >
                          Mark Paid
                        </button>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {/* ── EXPORTS ── */}
        {tab === "exports" && (
          <div className="space-y-4">
            <SectionLabel>Data Exports</SectionLabel>
            <div className="flex gap-2">
              <button
                onClick={() => fetchExport("csv").catch((err) => setMessage(err instanceof Error ? err.message : "Load failed"))}
                className="flex items-center gap-1.5 px-4 py-2.5 border border-border text-[11px] font-mono uppercase tracking-[0.1em] text-foreground hover:bg-foreground/5 transition-colors"
              >
                <Download className="w-3.5 h-3.5" /> Load CSV
              </button>
              <button
                onClick={() => fetchExport("json").catch((err) => setMessage(err instanceof Error ? err.message : "Load failed"))}
                className="flex items-center gap-1.5 px-4 py-2.5 border border-border text-[11px] font-mono uppercase tracking-[0.1em] text-foreground hover:bg-foreground/5 transition-colors"
              >
                <Download className="w-3.5 h-3.5" /> Load JSON
              </button>
            </div>
            <pre className="border border-border bg-card p-4 text-[11px] font-mono text-foreground/85 overflow-auto max-h-96 whitespace-pre-wrap">
              {exportText || "No export loaded yet. Click a button above to load session data."}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
}
