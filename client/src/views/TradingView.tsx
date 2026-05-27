import { useEffect, useMemo, useState } from "react";
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

export default function TradingView() {
  const navigate = useNavigate();
  const [state, setState] = useState<ParticipantState | null>(null);
  const [direction, setDirection] = useState<"yes" | "no">("yes");
  const [quantity, setQuantity] = useState(1);
  const [pricePath, setPricePath] = useState<number[]>([]);
  const [deadlineMs, setDeadlineMs] = useState<number | null>(null);
  const [error, setError] = useState("");
  const [submitting, setSubmitting] = useState(false);

  useEffect(() => {
    apiGet("/state")
      .then((s) => {
        const participantState = s as ParticipantState;
        setState(participantState);
        setPricePath([participantState.current_price ?? 0.5]);
      })
      .catch(() => {
        navigate("/");
      });
  }, [navigate]);

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
      setPricePath([payload.current_price]);
      setError("");
    }

    function onPriceUpdate(payload: PriceUpdateEvent) {
      setState((prev) => {
        if (!prev) return prev;
        return { ...prev, current_price: payload.current_price };
      });
      setPricePath((prev) => [...prev.slice(-39), payload.current_price]);
    }

    function onRoundEnded() {
      setDeadlineMs(null);
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

  const secondsLeft = useMemo(() => {
    if (!deadlineMs) return null;
    const raw = Math.floor((deadlineMs - Date.now()) / 1000);
    return raw > 0 ? raw : 0;
  }, [deadlineMs]);

  useEffect(() => {
    if (!deadlineMs) return;
    const t = setInterval(() => {
      if (Date.now() > deadlineMs) {
        setDeadlineMs(null);
      } else {
        setDeadlineMs((x) => x);
      }
    }, 500);
    return () => clearInterval(t);
  }, [deadlineMs]);

  async function submitTrade(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    if (!state || deadlineMs === null) return;
    setSubmitting(true);
    setError("");
    try {
      const res = (await apiPost("/trade", { direction, quantity: Number(quantity) })) as {
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
    return <div className="container-main">Loading state…</div>;
  }

  const estCost = (state.current_price || 0.5) * Number(quantity);

  return (
    <div className="container-main space-y-4">
      <div className="card">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h1 className="text-xl font-semibold">
            Market {state.current_market_number} • Round {state.current_round_number}
          </h1>
          <div className="text-sm font-medium text-cyan-800">
            {secondsLeft !== null ? `Time left: ${secondsLeft}s` : "Round closed"}
          </div>
        </div>
      </div>

      <div className="card">
        <h2 className="mb-2 text-lg font-medium">Narrative Bulletin</h2>
        <p className="text-sm text-slate-700">{state.bulletin?.public || "Awaiting round bulletin."}</p>
      </div>

      {state.bulletin?.analytical ? (
        <div className="card border-cyan-200 bg-cyan-50">
          <h2 className="mb-2 text-lg font-medium">Analyst Commentary</h2>
          <p className="text-sm">{state.bulletin.analytical}</p>
        </div>
      ) : null}

      {state.bulletin?.intelligence ? (
        <div className="card border-amber-300 bg-amber-50">
          <h2 className="mb-2 text-lg font-medium">Intelligence Brief</h2>
          <p className="text-sm">{state.bulletin.intelligence}</p>
        </div>
      ) : null}

      {state.posterior !== null && state.posterior !== undefined ? (
        <div className="card border-emerald-300 bg-emerald-50">
          <h2 className="mb-2 text-lg font-medium">Your Private Assessment</h2>
          <p className="text-sm font-semibold">P(YES) = {(state.posterior * 100).toFixed(1)}%</p>
        </div>
      ) : null}

      <div className="grid gap-4 md:grid-cols-2">
        <div className="card">
          <h2 className="mb-2 text-lg font-medium">Market State</h2>
          <p className="text-3xl font-semibold text-cyan-800">{((state.current_price || 0.5) * 100).toFixed(1)}%</p>
          <div className="mt-3 flex flex-wrap gap-1">
            {pricePath.map((p, idx) => (
              <div
                key={`${idx}-${p}`}
                className="h-6 w-2 rounded"
                style={{ backgroundColor: `rgba(8,145,178,${Math.max(0.2, p)})` }}
                title={`${(p * 100).toFixed(1)}%`}
              />
            ))}
          </div>
        </div>

        <div className="card">
          <h2 className="mb-2 text-lg font-medium">Portfolio</h2>
          <p className="text-sm">Balance: {Number(state.balance || 0).toFixed(2)} tokens</p>
          <p className="text-sm">YES held: {Number(state.yes_held || 0).toFixed(2)}</p>
          <p className="text-sm">NO held: {Number(state.no_held || 0).toFixed(2)}</p>
        </div>
      </div>

      <form className="card space-y-3" onSubmit={submitTrade}>
        <h2 className="text-lg font-medium">Trade</h2>
        <div className="flex gap-2">
          <button
            type="button"
            className={direction === "yes" ? "btn-primary" : "btn-secondary"}
            onClick={() => setDirection("yes")}
          >
            Buy YES
          </button>
          <button
            type="button"
            className={direction === "no" ? "btn-primary" : "btn-secondary"}
            onClick={() => setDirection("no")}
          >
            Buy NO
          </button>
        </div>
        <div>
          <label className="mb-1 block text-sm">Quantity (1-20)</label>
          <input
            type="number"
            min={1}
            max={20}
            value={quantity}
            onChange={(e) => setQuantity(Number(e.target.value))}
            className="w-40 rounded border border-slate-300 px-3 py-2"
          />
        </div>
        <p className="text-sm text-slate-600">Estimated immediate cost: {estCost.toFixed(2)} tokens</p>
        <button type="submit" className="btn-primary" disabled={submitting || deadlineMs === null}>
          {submitting ? "Submitting..." : "Submit Trade"}
        </button>
        {error ? <p className="text-sm text-red-700">{error}</p> : null}
      </form>
    </div>
  );
}
