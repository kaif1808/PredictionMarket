import { useState, useEffect, useRef, useCallback } from "react";
import {
  LineChart, Line, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
} from "recharts";

// ── Types ─────────────────────────────────────────────────────────────────────

interface Market {
  true_probability: number;
  outcome: number | null;
  b: number;
  round_duration_s: number;
  subject_count: number;
}

interface Bot {
  id: string;
  profile: string;
  role_tier: string;
  risk_aversion: number;
}

interface RoundSummary {
  round_number: number;
  opening_price: number;
  closing_price: number;
  benchmark: number;
  duration_s: number;
}

interface TradeEvent {
  round_number: number;
  event_time_s: number;
  t_ms: number;
  participant_id: string;
  profile: string;
  side: string;
  direction: string;
  quantity: number;
  price_before: number;
  price_after: number;
  q_yes_after: number;
  q_no_after: number;
  balance_after: number;
  yes_held: number;
  no_held: number;
  belief: number;
}

interface Payload {
  market: Market;
  bots: Bot[];
  rounds: RoundSummary[];
  trades: TradeEvent[];
}

// ── Helpers ───────────────────────────────────────────────────────────────────

const pct = (n: number) => `${(n * 100).toFixed(1)}%`;

// ── Component ─────────────────────────────────────────────────────────────────

export default function AbmWatch() {
  // ── Config state
  const [seed, setSeed] = useState(42);
  const [subjectCount, setSubjectCount] = useState(8);
  const [profileMix, setProfileMix] = useState("default");
  const [b, setB] = useState(10);

  // ── Data state
  const [payload, setPayload] = useState<Payload | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Playback state
  const [clock, setClock] = useState(0);
  const [playing, setPlaying] = useState(false);
  const [speed, setSpeed] = useState<1 | 2 | 4 | 8>(1);

  // ── RAF refs
  const rafRef = useRef<number | null>(null);
  const lastRafTime = useRef<number | null>(null);

  // ── Derived constants
  const totalDurationMs = payload ? payload.market.round_duration_s * 1000 * 5 : 0;
  const roundDurationMs = payload ? payload.market.round_duration_s * 1000 : 0;

  // ── Fetch
  const fetchPayload = useCallback(async (opts: {
    seed: number;
    subjectCount: number;
    profileMix: string;
    b: number;
  }) => {
    setLoading(true);
    setError(null);
    setPlaying(false);
    setClock(0);
    try {
      const params = new URLSearchParams({
        seed: String(opts.seed),
        subject_count: String(opts.subjectCount),
        profile_mix: opts.profileMix,
        b: String(opts.b),
        market_number: "1",
      });
      const res = await fetch(`/abm/watch/run?${params}`, { credentials: "include" });
      if (!res.ok) throw new Error(await res.text());
      setPayload(await res.json());
    } catch (e) {
      setError(e instanceof Error ? e.message : "fetch failed");
    } finally {
      setLoading(false);
    }
  }, []);

  // Fetch on mount
  useEffect(() => {
    fetchPayload({ seed, subjectCount, profileMix, b });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Regenerate
  const regenerate = useCallback(() => {
    const newSeed = Math.random() * 99999 | 0;
    setSeed(newSeed);
    fetchPayload({ seed: newSeed, subjectCount, profileMix, b });
  }, [fetchPayload, subjectCount, profileMix, b]);

  // ── RAF playback engine
  useEffect(() => {
    if (!playing) {
      lastRafTime.current = null;
      return;
    }
    const tick = (now: number) => {
      if (lastRafTime.current != null) {
        const elapsed = now - lastRafTime.current;
        setClock(c => Math.min(c + elapsed * speed, totalDurationMs));
      }
      lastRafTime.current = now;
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [playing, speed, totalDurationMs]);

  // ── Auto-pause at end
  useEffect(() => {
    if (clock >= totalDurationMs && totalDurationMs > 0 && playing) {
      setPlaying(false);
    }
  }, [clock, totalDurationMs, playing]);

  // ── Derived values
  const revealedTrades = payload ? payload.trades.filter(t => t.t_ms <= clock) : [];

  const currentRound = payload
    ? Math.min(5, Math.floor(clock / roundDurationMs) + 1)
    : 1;

  const currentPrice = revealedTrades.length > 0
    ? revealedTrades[revealedTrades.length - 1].price_after
    : 0.5;

  const chartData: Array<{ elapsedSec: number; price: number }> = payload
    ? [
        {
          elapsedSec: 0,
          price: payload.rounds[currentRound - 1]?.opening_price ?? 0.5,
        },
        ...revealedTrades
          .filter(t => t.round_number === currentRound)
          .map(t => ({ elapsedSec: t.event_time_s, price: t.price_after })),
      ]
    : [];

  const tradeFeed = [...revealedTrades].reverse().slice(0, 30);

  const botPositions = payload
    ? payload.bots
        .map(bot => {
          const botTrades = revealedTrades.filter(t => t.participant_id === bot.id);
          const last = botTrades[botTrades.length - 1];
          return {
            ...bot,
            balance: last?.balance_after ?? 100,
            yes_held: last?.yes_held ?? 0,
            no_held: last?.no_held ?? 0,
            belief: last?.belief ?? 0.5,
            pnl: (last?.balance_after ?? 100) - 100,
          };
        })
        .sort((a, bBot) => bBot.balance - a.balance)
    : [];

  // ── Render ────────────────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-background text-foreground p-6 space-y-6 max-w-5xl mx-auto">

      {/* Header controls */}
      <div className="flex items-center justify-between flex-wrap gap-4">
        <h1 className="text-lg font-mono tracking-tight">ABM · Bot Market Watch</h1>
        <div className="flex items-center gap-3 flex-wrap">
          <label className="flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground uppercase tracking-[0.15em]">
            Seed
            <input
              type="number"
              value={seed}
              onChange={e => setSeed(Number(e.target.value))}
              className="w-20 bg-transparent border-b border-border px-1 py-0.5 text-xs font-mono text-foreground focus:outline-none"
            />
          </label>
          <label className="flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground uppercase tracking-[0.15em]">
            Bots
            <input
              type="number"
              value={subjectCount}
              onChange={e => setSubjectCount(Number(e.target.value))}
              min={2}
              max={32}
              className="w-14 bg-transparent border-b border-border px-1 py-0.5 text-xs font-mono text-foreground focus:outline-none"
            />
          </label>
          <label className="flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground uppercase tracking-[0.15em]">
            Mix
            <input
              type="text"
              value={profileMix}
              onChange={e => setProfileMix(e.target.value)}
              className="w-20 bg-transparent border-b border-border px-1 py-0.5 text-xs font-mono text-foreground focus:outline-none"
            />
          </label>
          <label className="flex items-center gap-1.5 text-[10px] font-mono text-muted-foreground uppercase tracking-[0.15em]">
            b
            <input
              type="number"
              value={b}
              onChange={e => setB(Number(e.target.value))}
              min={1}
              className="w-14 bg-transparent border-b border-border px-1 py-0.5 text-xs font-mono text-foreground focus:outline-none"
            />
          </label>
          <button
            onClick={regenerate}
            disabled={loading}
            className="px-3 py-1.5 border border-border text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground hover:text-foreground hover:border-foreground/50 transition-colors disabled:opacity-40"
          >
            {loading ? "Loading…" : "Regenerate"}
          </button>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="border border-red-500/50 bg-red-500/10 p-3 text-xs font-mono text-red-400">
          {error}
        </div>
      )}

      {/* Loading skeleton */}
      {loading && (
        <div className="border border-border p-8 flex items-center justify-center">
          <span className="text-xs font-mono text-muted-foreground animate-pulse">Simulating…</span>
        </div>
      )}

      {payload && !loading && (
        <>
          {/* Market header */}
          <div className="border border-border p-4 space-y-1">
            <div className="flex items-baseline gap-4 flex-wrap">
              <span className="text-3xl font-mono tabular-nums">{pct(currentPrice)}</span>
              <span className="text-xs font-mono text-muted-foreground">P(YES)</span>
              <span className="text-xs font-mono text-muted-foreground">Round {currentRound}/5</span>
              <span className="text-xs font-mono text-muted-foreground">
                True P: {pct(payload.market.true_probability)}
              </span>
              <span className="text-xs font-mono text-muted-foreground">
                b={payload.market.b} · {payload.market.subject_count} bots
              </span>
              {clock >= totalDurationMs && totalDurationMs > 0 && (
                <span className="text-xs font-mono border border-border px-2 py-0.5">
                  Outcome: {payload.market.outcome === 1 ? "YES" : "NO"}
                </span>
              )}
            </div>
            {/* Round summary strip */}
            <div className="flex gap-3 flex-wrap pt-1">
              {payload.rounds.map(r => (
                <span key={r.round_number} className="text-[10px] font-mono text-muted-foreground/60">
                  R{r.round_number}: {pct(r.opening_price)}→{pct(r.closing_price)}
                  {" "}(bmk {pct(r.benchmark)})
                </span>
              ))}
            </div>
          </div>

          {/* Price chart */}
          <div className="border border-border p-4">
            <p className="text-[10px] font-mono text-muted-foreground/60 uppercase tracking-[0.15em] mb-3">
              Round {currentRound} · Price path
            </p>
            <div className="h-40 mb-3 w-full">
              <ResponsiveContainer width="100%" height={160}>
                <LineChart data={chartData} margin={{ top: 4, right: 38, left: 0, bottom: 0 }}>
                  <CartesianGrid strokeDasharray="1 8" stroke="rgba(148,163,184,0.08)" vertical={false} />
                  <XAxis
                    dataKey="elapsedSec"
                    type="number"
                    domain={[0, roundDurationMs / 1000]}
                    allowDataOverflow
                    tickFormatter={(value: number) => `${value}s`}
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
                    content={({ active, payload: tp }) =>
                      active && tp?.length ? (
                        <div className="border border-border bg-background px-2.5 py-1.5 text-[11px] font-mono text-foreground/80">
                          t={tp[0].payload?.elapsedSec ?? 0}s · P(YES) = {((tp[0].value as number) * 100).toFixed(2)}%
                        </div>
                      ) : null
                    }
                  />
                  <Line
                    type="linear"
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
            <div className="flex gap-4">
              {[
                { label: "YES", p: currentPrice, col: "bg-green-500", track: "bg-green-500/12", text: "text-green-400" },
                { label: "NO",  p: 1 - currentPrice, col: "bg-red-500",   track: "bg-red-500/12",   text: "text-red-400"   },
              ].map(({ label, p, col, track, text }) => (
                <div key={label} className="flex items-center gap-2 flex-1">
                  <span className={`text-[10px] font-mono ${text} w-6 shrink-0`}>{label}</span>
                  <div className={`flex-1 h-0.5 rounded-full ${track} overflow-hidden`}>
                    <div
                      className={`h-full rounded-full ${col} transition-all duration-700`}
                      style={{ width: pct(p) }}
                    />
                  </div>
                  <span className={`text-[11px] font-mono tabular-nums ${text} w-9 text-right`}>{pct(p)}</span>
                </div>
              ))}
            </div>
          </div>

          {/* Playback controls */}
          <div className="border border-border p-4 flex items-center gap-3 flex-wrap">
            <button
              onClick={() => setPlaying(p => !p)}
              className="px-3 py-1.5 border border-border text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground hover:text-foreground hover:border-foreground/50 transition-colors w-16 text-center"
            >
              {playing ? "Pause" : "Play"}
            </button>

            {/* Speed toggles */}
            <div className="flex items-center gap-1">
              {([1, 2, 4, 8] as const).map(s => (
                <button
                  key={s}
                  onClick={() => setSpeed(s)}
                  className={`px-2 py-1 text-[10px] font-mono border transition-colors ${
                    speed === s
                      ? "border-foreground/60 text-foreground"
                      : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  x{s}
                </button>
              ))}
            </div>

            {/* Seek slider */}
            <input
              type="range"
              min={0}
              max={totalDurationMs}
              value={clock}
              onChange={e => {
                setPlaying(false);
                setClock(Number(e.target.value));
              }}
              className="flex-1 min-w-32 accent-green-500"
            />

            {/* Round jump buttons */}
            <div className="flex items-center gap-1">
              {[1, 2, 3, 4, 5].map(r => (
                <button
                  key={r}
                  onClick={() => {
                    setPlaying(false);
                    setClock((r - 1) * roundDurationMs);
                  }}
                  className={`px-2 py-1 text-[10px] font-mono border transition-colors ${
                    currentRound === r
                      ? "border-foreground/60 text-foreground"
                      : "border-border text-muted-foreground hover:text-foreground"
                  }`}
                >
                  R{r}
                </button>
              ))}
            </div>

            <span className="text-[10px] font-mono text-muted-foreground tabular-nums">
              {(clock / 1000).toFixed(1)}s / {(totalDurationMs / 1000).toFixed(0)}s
            </span>
          </div>

          {/* Trade feed + Bot positions */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

            {/* Trade feed */}
            <div className="border border-border p-4">
              <p className="text-xs font-mono text-muted-foreground mb-3 uppercase tracking-[0.12em]">
                Trade Feed
                <span className="ml-2 text-muted-foreground/40">({revealedTrades.length} total)</span>
              </p>
              <div className="space-y-1 max-h-64 overflow-y-auto">
                {tradeFeed.length === 0 && (
                  <p className="text-[10px] font-mono text-muted-foreground/40">No trades yet</p>
                )}
                {tradeFeed.map((t, i) => (
                  <div key={i} className="flex items-center gap-2 text-[11px] font-mono">
                    <span className="text-muted-foreground/40 w-6 shrink-0">{t.participant_id}</span>
                    <span className="px-1 border border-border text-[9px] text-muted-foreground/60 shrink-0">
                      {t.profile}
                    </span>
                    <span className={t.side === "buy" ? "text-green-400" : "text-red-400"}>
                      {t.side.toUpperCase()}
                    </span>
                    <span className="text-muted-foreground/80">{t.direction.toUpperCase()}</span>
                    <span className="tabular-nums">{t.quantity}</span>
                    <span className="text-muted-foreground/40 tabular-nums">
                      {pct(t.price_before)}→{pct(t.price_after)}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Bot positions */}
            <div className="border border-border p-4">
              <p className="text-xs font-mono text-muted-foreground mb-3 uppercase tracking-[0.12em]">
                Bot Positions
              </p>
              <div className="space-y-1.5">
                {botPositions.map(bot => (
                  <div key={bot.id} className="flex items-center gap-2 text-[11px] font-mono flex-wrap">
                    <span className="w-6 text-muted-foreground/60 shrink-0">{bot.id}</span>
                    <span className="px-1 border border-border text-[9px] text-muted-foreground/60 shrink-0">
                      {bot.profile}
                    </span>
                    <span className="text-muted-foreground/50">
                      B:{bot.belief.toFixed(2)}
                    </span>
                    <span className="tabular-nums">${bot.balance.toFixed(1)}</span>
                    <span className="text-green-400 tabular-nums">Y:{bot.yes_held.toFixed(0)}</span>
                    <span className="text-red-400 tabular-nums">N:{bot.no_held.toFixed(0)}</span>
                    <span className={bot.pnl >= 0 ? "text-green-400 tabular-nums" : "text-red-400 tabular-nums"}>
                      PnL:{bot.pnl >= 0 ? "+" : ""}{bot.pnl.toFixed(1)}
                    </span>
                  </div>
                ))}
              </div>
            </div>

          </div>
        </>
      )}
    </div>
  );
}
