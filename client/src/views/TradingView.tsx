import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet, apiPost } from "../lib/api";
import { getSocket } from "../lib/socket";
import type {
  ErrorEvent,
  MarketResolvedEvent,
  ParticipantState,
  PriceUpdateEvent,
  RoundStartedEvent
} from "../types/events";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";
import {
  Eye, Shield, Lock, Clock, TrendingUp, TrendingDown, AlertTriangle,
} from "lucide-react";
import { CountdownBadge } from "../components/CountdownBadge";
import { SectionLabel } from "../components/SectionLabel";

// ── IntelPanel ────────────────────────────────────────────────────────────────
function IntelPanel({
  tier, title, icon, body, lockedMsg,
}: {
  tier: "public" | "analytical" | "intelligence";
  title: string;
  icon: React.ReactNode;
  body: string | null | undefined;
  lockedMsg?: string;
}) {
  const accent = {
    public:       { bar: "bg-muted-foreground/25", label: "text-muted-foreground/50" },
    analytical:   { bar: "bg-cyan-500/50",          label: "text-cyan-400/60"          },
    intelligence: { bar: "bg-amber-500/50",         label: "text-amber-400/60"         },
  }[tier];

  return (
    <div className={`border-t border-border py-4 pl-4 relative ${!body ? "opacity-40" : ""}`}>
      <div className={`absolute left-0 top-4 bottom-4 w-0.5 ${accent.bar}`} />
      <div className="flex items-center gap-1.5 mb-2">
        <span className={`${accent.label} flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-[0.18em]`}>
          {icon}
          {title}
        </span>
        {!body && lockedMsg && (
          <span className="ml-auto text-[9px] font-mono text-muted-foreground/30 uppercase tracking-[0.15em]">
            restricted
          </span>
        )}
      </div>
      {body ? (
        <p className="text-[13px] leading-relaxed text-foreground/75" style={{ fontFamily: "Spectral, Georgia, serif" }}>
          {body}
        </p>
      ) : (
        <p className="text-[11px] font-mono text-muted-foreground/30 italic">{lockedMsg}</p>
      )}
    </div>
  );
}

export default function TradingView() {
  const ROUND_DURATION_SECONDS = 90;
  const ROUND_DURATION_MS = ROUND_DURATION_SECONDS * 1000;
  const navigate = useNavigate();
  const [state, setState] = useState<ParticipantState | null>(null);
  const [direction, setDirection] = useState<"yes" | "no">("yes");
  const [quantity, setQuantity] = useState(1);
  const [pricePath, setPricePath] = useState<Array<{ elapsedSec: number; price: number }>>([]);
  const [deadlineMs, setDeadlineMs] = useState<number | null>(null);
  const [roundStartMs, setRoundStartMs] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [mode, setMode] = useState<"buy" | "sell">("buy");
  const [secondsLeft, setSecondsLeft] = useState<number | null>(null);
  const livePrice = state?.current_price ?? 0.5;

  function seedChartFromState(participantState: ParticipantState) {
    const currentPrice = participantState.current_price ?? 0.5;
    if (participantState.phase === "round_open" && participantState.round_deadline_unix_ms !== null) {
      const seedDeadlineMs = participantState.round_deadline_unix_ms;
      const seedRoundStartMs = seedDeadlineMs - ROUND_DURATION_MS;
      const seedElapsedSec = Math.max(0, Math.floor((Date.now() - seedRoundStartMs) / 1000));
      setDeadlineMs(seedDeadlineMs);
      setRoundStartMs(seedRoundStartMs);
      setPricePath([{ elapsedSec: seedElapsedSec, price: currentPrice }]);
      return;
    }
    setDeadlineMs(null);
    setRoundStartMs(null);
    setPricePath([{ elapsedSec: 0, price: currentPrice }]);
  }

  // Initial state fetch
  useEffect(() => {
    apiGet("/state")
      .then((s) => {
        const participantState = s as ParticipantState;
        setState(participantState);
        seedChartFromState(participantState);
      })
      .catch(() => {
        navigate("/");
      });
  }, [navigate]);

  // Socket subscriptions — preserved verbatim
  useEffect(() => {
    const socket = getSocket();

    function onRoundStarted(payload: RoundStartedEvent) {
      setState((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          current_round_number: payload.round_number,
          current_price: payload.current_price,
          balance: payload.balance,
          yes_held: payload.yes_held,
          no_held: payload.no_held,
          bulletin: payload.bulletin,
          posterior: payload.posterior
        };
      });
      setDeadlineMs(payload.round_deadline_unix_ms);
      const startedAtMs = payload.round_deadline_unix_ms - ROUND_DURATION_MS;
      setRoundStartMs(startedAtMs);
      setPricePath([
        {
          elapsedSec: Math.max(0, Math.floor((Date.now() - startedAtMs) / 1000)),
          price: payload.current_price
        }
      ]);
      setError("");
    }

    function onPriceUpdate(payload: PriceUpdateEvent) {
      setState((prev) => {
        if (!prev) return prev;
        return { ...prev, current_price: payload.current_price };
      });
    }

    function onRoundEnded() {
      setDeadlineMs(null);
      setRoundStartMs(null);
    }

    function onMarketResolved(_payload: MarketResolvedEvent) {
      navigate("/lobby");
    }

    function onSessionClosed(_payload: { session_id: number }) {
      navigate("/debrief");
    }

    function onError(payload: ErrorEvent) {
      setError(payload?.message || "Trade rejected");
      setSubmitting(false);
    }

    function onStateSync(payload: ParticipantState) {
      setState(payload);
      seedChartFromState(payload);
    }

    socket.on("round_started", onRoundStarted);
    socket.on("price_update", onPriceUpdate);
    socket.on("round_ended", onRoundEnded);
    socket.on("market_resolved", onMarketResolved);
    socket.on("session_closed", onSessionClosed);
    socket.on("state_sync", onStateSync);
    socket.on("error", onError);

    return () => {
      socket.off("round_started", onRoundStarted);
      socket.off("price_update", onPriceUpdate);
      socket.off("round_ended", onRoundEnded);
      socket.off("market_resolved", onMarketResolved);
      socket.off("session_closed", onSessionClosed);
      socket.off("state_sync", onStateSync);
      socket.off("error", onError);
    };
  }, [navigate]);

  // Countdown timer
  useEffect(() => {
    if (!deadlineMs) {
      setSecondsLeft(null);
      return;
    }
    function tick() {
      const raw = Math.floor((deadlineMs! - Date.now()) / 1000);
      setSecondsLeft(raw > 0 ? raw : 0);
      if (Date.now() > deadlineMs!) {
        setDeadlineMs(null);
        setRoundStartMs(null);
      }
    }
    tick();
    const t = setInterval(tick, 500);
    return () => clearInterval(t);
  }, [deadlineMs]);

  useEffect(() => {
    if (deadlineMs === null || roundStartMs === null) return;
    const startMs = roundStartMs;
    function appendSample() {
      const elapsedSec = Math.max(0, Math.floor((Date.now() - startMs) / 1000));
      setPricePath((prev) => {
        if (prev.length === 0) return [{ elapsedSec, price: livePrice }];
        const last = prev[prev.length - 1];
        if (last.elapsedSec === elapsedSec) {
          if (last.price === livePrice) return prev;
          return [...prev.slice(0, -1), { elapsedSec, price: livePrice }];
        }
        return [...prev, { elapsedSec, price: livePrice }];
      });
    }
    appendSample();
    const ticker = setInterval(appendSample, 1000);
    return () => clearInterval(ticker);
  }, [deadlineMs, roundStartMs, livePrice]);

  // Trade submit
  async function submitTrade(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!state || deadlineMs === null) return;
    setSubmitting(true);
    setError("");
    try {
      const res = (await apiPost("/trade", { side: mode, direction, quantity: Number(quantity) })) as {
        balance_after: number;
        yes_held: number;
        no_held: number;
      };
      setState((prev) => {
        if (!prev) return prev;
        return {
          ...prev,
          balance: res.balance_after,
          yes_held: res.yes_held,
          no_held: res.no_held
        };
      });
    } catch (err) {
      const message = err instanceof Error ? err.message : "Trade failed";
      setError(message);
    } finally {
      setSubmitting(false);
    }
  }

  if (!state) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-sm font-mono text-muted-foreground animate-pulse">Loading state…</p>
      </div>
    );
  }

  const currentPrice = livePrice;
  const chartData = pricePath;
  const pct = (n: number) => `${(n * 100).toFixed(1)}%`;
  const tradingOpen = deadlineMs !== null;
  const isSell = mode === "sell";
  const yesHeld = Number(state.yes_held || 0);
  const noHeld = Number(state.no_held || 0);
  const held = direction === "yes" ? yesHeld : noHeld;
  const maxQty = isSell ? held : 20;
  const balance = Number(state.balance || 0);
  const estCost = currentPrice * Number(quantity);
  const canExecute = isSell ? held >= quantity : estCost <= balance;

  return (
    <div className="min-h-screen flex flex-col">
      {/* Header */}
      <header className="border-b border-border shrink-0">
        <div className="max-w-7xl mx-auto px-5 h-11 flex items-center justify-between gap-6">
          <div className="flex items-center gap-4 min-w-0">
            <div className="flex items-center gap-1.5 shrink-0">
              <span className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
              <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-green-500/70">Live</span>
            </div>
            <span className="text-border">·</span>
            <span className="text-[11px] font-mono text-foreground/70">
              Market {state.current_market_number}
            </span>
            <span className="text-border hidden sm:block">·</span>
            <span className="text-[11px] font-mono text-muted-foreground/50 hidden sm:block">
              Round {state.current_round_number} / 5
            </span>
          </div>
          <CountdownBadge seconds={secondsLeft} />
        </div>
      </header>

      {/* Body */}
      <div className="flex-1 max-w-7xl mx-auto w-full px-5 py-6">
        <div className="grid grid-cols-1 lg:grid-cols-[1fr_320px] gap-8">

          {/* Left column */}
          <div>
            {/* Market price */}
            <div className="mb-5">
              <h2
                className="text-xl font-light leading-snug text-foreground/90 mb-4"
                style={{ fontFamily: "Spectral, Georgia, serif" }}
              >
                Will Valdoria enter armed conflict with Norheim within 12 months of the Karvač incident?
              </h2>
              <div className="flex items-baseline gap-3">
                <span className="text-5xl font-mono font-semibold tabular-nums tracking-tight">
                  {pct(currentPrice)}
                </span>
                <span className="text-xs font-mono text-muted-foreground/40 ml-1">chance · LMSR</span>
              </div>
            </div>

            {/* Recharts LineChart */}
            <div className="h-40 mb-3 w-full">
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={chartData} margin={{ top: 4, right: 38, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="1 8" stroke="rgba(148,163,184,0.08)" vertical={false} />
                  <XAxis
                    dataKey="elapsedSec"
                    type="number"
                    domain={["dataMin", "dataMax"]}
                    tickFormatter={(value) => `${value}s`}
                    tick={{ fill: "var(--muted-foreground)", fontSize: 9, fontFamily: "JetBrains Mono, monospace" }}
                    axisLine={false}
                    tickLine={false}
                    height={16}
                  />
                  <YAxis
                    domain={[0, 1]}
                    orientation="right"
                    ticks={[0, 0.25, 0.5, 0.75, 1]}
                    tickFormatter={(v: number) => `${(v * 100).toFixed(0)}%`}
                    tick={{ fill: "var(--muted-foreground)", fontSize: 9, fontFamily: "JetBrains Mono, monospace" }}
                    axisLine={false}
                    tickLine={false}
                    width={32}
                  />
                  <Tooltip
                    content={({ active, payload }) =>
                      active && payload?.length ? (
                        <div className="border border-border bg-background px-2.5 py-1.5 text-[11px] font-mono text-foreground/80">
                          t={payload[0].payload?.elapsedSec ?? 0}s · P(YES) = {((payload[0].value as number) * 100).toFixed(2)}%
                        </div>
                      ) : null
                    }
                  />
                  <Line
                    type="stepAfter"
                    dataKey="price"
                    stroke="#22c55e"
                    strokeWidth={1.5}
                    dot={false}
                    isAnimationActive={false}
                    activeDot={{ r: 3.5, fill: "#22c55e", strokeWidth: 2 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>

            {/* YES/NO bars */}
            <div className="flex gap-4 mb-7 pb-5 border-b border-border">
              {[
                { label: "YES", p: currentPrice, col: "bg-green-500", track: "bg-green-500/12", text: "text-green-400" },
                { label: "NO",  p: 1 - currentPrice, col: "bg-red-500", track: "bg-red-500/12", text: "text-red-400" },
              ].map(({ label, p, col, track, text }) => (
                <div key={label} className="flex items-center gap-2 flex-1">
                  <span className={`text-[10px] font-mono ${text} w-6 shrink-0`}>{label}</span>
                  <div className={`flex-1 h-0.5 rounded-full ${track} overflow-hidden`}>
                    <div className={`h-full rounded-full ${col} transition-all duration-700`} style={{ width: pct(p) }} />
                  </div>
                  <span className={`text-[11px] font-mono tabular-nums ${text} w-9 text-right`}>{pct(p)}</span>
                </div>
              ))}
            </div>

            {/* Intel briefings */}
            <div className="space-y-0">
              <IntelPanel
                tier="public"
                title="Situation Report"
                icon={<Eye className="w-3 h-3" />}
                body={state.bulletin?.public}
                lockedMsg="No bulletin available."
              />
              <IntelPanel
                tier="analytical"
                title="Analyst Commentary"
                icon={<Shield className="w-3 h-3" />}
                body={state.bulletin?.analytical}
                lockedMsg="Analyst commentary not available at your clearance level."
              />
              <IntelPanel
                tier="intelligence"
                title="Intelligence Brief"
                icon={<Lock className="w-3 h-3" />}
                body={state.bulletin?.intelligence}
                lockedMsg="Intelligence briefs are restricted to senior analysts."
              />

              {/* Private posterior */}
              {state.posterior !== null && state.posterior !== undefined && (
                <div className="border-t border-border pt-5 mt-1">
                  <div className="flex items-center justify-between mb-3">
                    <div className="flex items-center gap-2">
                      <span className="w-1 h-1 rounded-full bg-amber-400 inline-block" />
                      <span className="text-[10px] font-mono uppercase tracking-[0.2em] text-amber-400/60">
                        Private Assessment
                      </span>
                    </div>
                  </div>
                  <div className="flex items-baseline gap-3 mb-3">
                    <span className="text-[11px] font-mono text-muted-foreground/40 uppercase tracking-[0.1em]">P(YES | signals)</span>
                    <span className="text-3xl font-mono font-semibold text-amber-300 tabular-nums">
                      {pct(state.posterior)}
                    </span>
                  </div>
                  <div className="relative h-px bg-amber-500/10 overflow-visible mb-1">
                    <div
                      className="absolute top-0 left-0 h-full bg-amber-400/60 transition-all duration-700"
                      style={{ width: pct(state.posterior) }}
                    />
                    <div className="absolute top-[-3px] h-[7px] w-px bg-amber-300/30" style={{ left: "50%" }} />
                  </div>
                  <p className="text-[10px] font-mono text-muted-foreground/35 mt-2.5 leading-relaxed">
                    Your private signal posterior — not visible to other participants.
                  </p>
                </div>
              )}
            </div>
          </div>

          {/* Right column */}
          <div className="space-y-6">
            {/* Position */}
            <div>
              <SectionLabel>Position</SectionLabel>
              <div className="grid grid-cols-3 divide-x divide-border border border-border">
                {[
                  { label: "Balance", value: balance.toFixed(1), unit: "T", color: "" },
                  { label: "YES", value: String(yesHeld), unit: "contracts", color: "text-green-500" },
                  { label: "NO",  value: String(noHeld),  unit: "contracts", color: noHeld > 0 ? "text-red-500" : "text-muted-foreground/60" },
                ].map(({ label, value, unit, color }) => (
                  <div key={label} className="px-4 py-3.5">
                    <p className="text-[9px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-1.5">{label}</p>
                    <p className={`text-xl font-mono font-medium tabular-nums ${color || "text-foreground"}`}>
                      {value}
                      <span className="text-[10px] font-normal text-muted-foreground ml-1">{unit}</span>
                    </p>
                  </div>
                ))}
              </div>
            </div>

            {/* Trade form */}
            <div>
              <SectionLabel>Trade</SectionLabel>
              <div className="border border-border">
                {!tradingOpen ? (
                  <div className="px-4 py-5 text-center">
                    <p className="text-xs font-mono text-red-400/70">Round closed — awaiting next round</p>
                  </div>
                ) : (
                  <form onSubmit={submitTrade} className="divide-y divide-border">
                    {/* BUY / SELL toggle */}
                    <div className="grid grid-cols-2 divide-x divide-border">
                      {(["buy", "sell"] as const).map((m) => (
                        <button
                          key={m}
                          type="button"
                          onClick={() => { setMode(m); setQuantity(1); }}
                          className={`py-2.5 text-[10px] font-mono uppercase tracking-[0.2em] transition-colors ${
                            mode === m ? "bg-foreground/8 text-foreground" : "text-muted-foreground hover:text-foreground"
                          }`}
                        >
                          {m}
                        </button>
                      ))}
                    </div>

                    {/* YES / NO direction */}
                    <div className="grid grid-cols-2 divide-x divide-border">
                      <button
                        type="button"
                        onClick={() => { setDirection("yes"); setQuantity(1); }}
                        className={`py-3.5 text-sm font-semibold flex items-center justify-center gap-1.5 transition-all ${
                          direction === "yes" ? "bg-green-500 text-white" : "text-green-600 dark:text-green-400 hover:bg-green-500/8"
                        }`}
                      >
                        <TrendingUp className="w-3.5 h-3.5" />
                        YES
                      </button>
                      <button
                        type="button"
                        onClick={() => { setDirection("no"); setQuantity(1); }}
                        className={`py-3.5 text-sm font-semibold flex items-center justify-center gap-1.5 transition-all ${
                          direction === "no" ? "bg-red-500 text-white" : "text-red-600 dark:text-red-400 hover:bg-red-500/8"
                        }`}
                      >
                        <TrendingDown className="w-3.5 h-3.5" />
                        NO
                      </button>
                    </div>

                    {/* Quantity */}
                    <div className="px-4 py-4">
                      {isSell && (
                        <p className="text-[10px] font-mono text-muted-foreground mb-3">
                          Holdings: <span className={held === 0 ? "text-red-500" : "text-foreground"}>{held} {direction.toUpperCase()}</span>
                        </p>
                      )}
                      <p className="text-[9px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-2.5">
                        Quantity {isSell ? `(max ${maxQty})` : "(1–20)"}
                      </p>
                      <div className="flex items-center border border-border">
                        <button
                          type="button"
                          onClick={() => setQuantity((q) => Math.max(1, q - 1))}
                          className="w-10 h-10 text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition-colors text-lg font-light border-r border-border flex items-center justify-center"
                        >
                          −
                        </button>
                        <input
                          type="number"
                          min={1}
                          max={maxQty}
                          value={quantity}
                          onChange={(e) => setQuantity(Math.min(maxQty, Math.max(1, parseInt(e.target.value) || 1)))}
                          className="flex-1 text-center bg-transparent py-2 font-mono text-base focus:outline-none text-foreground/90"
                        />
                        <button
                          type="button"
                          onClick={() => setQuantity((q) => Math.min(maxQty, q + 1))}
                          className="w-10 h-10 text-muted-foreground hover:text-foreground hover:bg-foreground/5 transition-colors text-lg font-light border-l border-border flex items-center justify-center"
                        >
                          +
                        </button>
                      </div>
                    </div>

                    {/* Cost preview */}
                    <div className="px-4 py-3 space-y-2">
                      <div className="flex justify-between items-baseline">
                        <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-[0.1em]">
                          Est. {isSell ? "receive" : "cost"}
                        </span>
                        <span className={`text-[11px] font-mono tabular-nums ${!canExecute ? "text-red-500" : "text-foreground"}`}>
                          {estCost.toFixed(2)} T
                        </span>
                      </div>
                      <div className="flex justify-between items-baseline">
                        <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-[0.1em]">Balance</span>
                        <span className="text-[11px] font-mono tabular-nums text-foreground">{balance.toFixed(1)} T</span>
                      </div>
                    </div>

                    {/* Validation */}
                    {!canExecute && (
                      <div className="flex items-center gap-2 px-4 py-2.5 bg-red-500/5 border-t border-red-500/15">
                        <AlertTriangle className="w-3 h-3 text-red-400/70 shrink-0" />
                        <span className="text-[10px] font-mono text-red-400/70">
                          {isSell ? `No ${direction.toUpperCase()} contracts to sell` : "Insufficient balance"}
                        </span>
                      </div>
                    )}

                    {error && (
                      <div className="flex items-center gap-2 px-4 py-2.5 bg-red-500/5">
                        <AlertTriangle className="w-3 h-3 text-red-400/70 shrink-0" />
                        <span className="text-[10px] font-mono text-red-400/70">{error}</span>
                      </div>
                    )}

                    {/* Submit */}
                    <button
                      type="submit"
                      disabled={submitting || !canExecute}
                      className={`w-full py-4 text-xs font-mono uppercase tracking-[0.2em] transition-all ${
                        !canExecute || submitting
                          ? "text-muted-foreground/60 cursor-not-allowed"
                          : direction === "yes"
                          ? "bg-green-500 text-white hover:bg-green-400"
                          : "bg-red-500 text-white hover:bg-red-400"
                      }`}
                    >
                      {submitting
                        ? "Submitting..."
                        : `${isSell ? "Sell" : "Buy"} ${quantity} ${direction.toUpperCase()} · ${estCost.toFixed(2)} T`}
                    </button>
                  </form>
                )}
              </div>
            </div>

            {/* Market metadata */}
            <div className="border-t border-border pt-4 space-y-2">
              {[
                ["Market", String(state.current_market_number ?? "—")],
                ["Round", String(state.current_round_number ?? "—")],
                ["Price", pct(currentPrice)],
              ].map(([k, v]) => (
                <div key={k} className="flex justify-between">
                  <span className="text-[10px] font-mono text-muted-foreground uppercase tracking-[0.1em]">{k}</span>
                  <span className="text-[10px] font-mono text-foreground/80">{v}</span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
