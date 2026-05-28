import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiPost } from "../../lib/api";
import { FlowShell } from "../../components/FlowShell";
import { AlertTriangle } from "lucide-react";

const HL_ROWS = Array.from({ length: 10 }, (_, i) => {
  const n = i + 1;
  const p = n / 10;
  return {
    n,
    pPct: `${n * 10}%`,
    eA: +(2.0 * p + 1.6 * (1 - p)).toFixed(2),
    eB: +(3.85 * p + 0.1 * (1 - p)).toFixed(2),
  };
});

export default function HoltLauryScreen() {
  const navigate = useNavigate();
  const [choices, setChoices] = useState(() =>
    Object.fromEntries(HL_ROWS.map((r) => [r.n, null]))
  );
  const [warning, setWarning] = useState(false);
  const [validationError, setValidationError] = useState("");

  function isMonotone() {
    let sawB = false;
    for (const r of HL_ROWS) {
      if (choices[r.n] === "B") sawB = true;
      if (sawB && choices[r.n] === "A") return false;
    }
    return true;
  }

  const switchPoint = useMemo(
    () => HL_ROWS.find((r) => choices[r.n] === "B")?.n ?? null,
    [choices]
  );

  async function handleSubmit() {
    const firstIncomplete = HL_ROWS.find((row) => choices[row.n] !== "A" && choices[row.n] !== "B");
    if (firstIncomplete) {
      setValidationError(`Please answer row ${firstIncomplete.n} before submitting.`);
      return;
    }
    setValidationError("");

    const monotone = isMonotone();
    if (!monotone) {
      setWarning(true);
    } else {
      setWarning(false);
    }
    // Always submit regardless of monotonicity
    await apiPost("/risk_elicitation/submit", {
      instrument: "holt_laury_10",
      switch_point: switchPoint,
      raw_choices: choices,
    });
    navigate("/lobby");
  }

  return (
    <FlowShell step={4} total={5} title="Risk Preference Elicitation">
      <p className="text-sm leading-relaxed text-foreground/75 mb-6" style={{ fontFamily: "Spectral, Georgia, serif" }}>
        For each row, choose Option A (safer) or Option B (riskier). Option A pays more reliably; Option B has a higher upside but a lower floor. Payoffs are in tokens.
      </p>

      <div className="border border-border overflow-hidden mb-4">
        {/* Table header */}
        <div className="grid grid-cols-[2rem_1fr_1fr_1fr] border-b border-border bg-card/60">
          <div className="px-3 py-2 text-[9px] font-mono uppercase tracking-[0.15em] text-muted-foreground border-r border-border">#</div>
          <div className="px-3 py-2 text-[9px] font-mono uppercase tracking-[0.15em] text-muted-foreground border-r border-border">Option A</div>
          <div className="px-3 py-2 text-[9px] font-mono uppercase tracking-[0.15em] text-muted-foreground border-r border-border">Option B</div>
          <div className="px-3 py-2 text-[9px] font-mono uppercase tracking-[0.15em] text-muted-foreground text-center">Choice</div>
        </div>
        {HL_ROWS.map((row) => {
          const sel = choices[row.n];
          return (
            <div
              key={row.n}
              className={`grid grid-cols-[2rem_1fr_1fr_1fr] border-b border-border last:border-b-0 transition-colors ${
                sel === "B" ? "bg-foreground/3" : ""
              }`}
            >
              <div className="px-3 py-2.5 text-[10px] font-mono tabular-nums text-muted-foreground border-r border-border flex items-center">
                {row.n}
              </div>
              <div className="px-3 py-2.5 text-[11px] font-mono border-r border-border">
                <span className="text-foreground">{row.pPct}</span>
                <span className="text-muted-foreground"> → 2.00 T</span>
                <br />
                <span className="text-foreground">{100 - row.n * 10}%</span>
                <span className="text-muted-foreground"> → 1.60 T</span>
              </div>
              <div className="px-3 py-2.5 text-[11px] font-mono border-r border-border">
                <span className="text-foreground">{row.pPct}</span>
                <span className="text-muted-foreground"> → 3.85 T</span>
                <br />
                <span className="text-foreground">{100 - row.n * 10}%</span>
                <span className="text-muted-foreground"> → 0.10 T</span>
              </div>
              <div className="flex items-center justify-center gap-3 px-3">
                {(["A", "B"]).map((opt) => (
                  <label key={opt} className="flex items-center gap-1 cursor-pointer">
                    <input
                      type="radio"
                      name={`row-${row.n}`}
                      className="sr-only"
                      checked={sel === opt}
                      onChange={() => {
                        setChoices((c) => ({ ...c, [row.n]: opt }));
                        setWarning(false);
                        setValidationError("");
                      }}
                    />
                    <div
                      className={`w-4 h-4 border flex items-center justify-center transition-colors ${
                        sel === opt ? "border-foreground bg-foreground" : "border-border"
                      }`}
                    >
                      {sel === opt && <div className="w-1.5 h-1.5 rounded-full bg-background" />}
                    </div>
                    <span className={`text-[11px] font-mono ${sel === opt ? "text-foreground" : "text-muted-foreground"}`}>{opt}</span>
                  </label>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {switchPoint !== null && (
        <p className="text-[10px] font-mono text-muted-foreground mb-4">
          Switch point: row {switchPoint} — switching from A to B at {switchPoint * 10}% probability.
        </p>
      )}

      {validationError && (
        <div className="flex items-start gap-2 border border-red-500/25 bg-red-500/5 px-4 py-3 mb-4">
          <AlertTriangle className="w-3.5 h-3.5 text-red-400 shrink-0 mt-0.5" />
          <p className="text-xs font-mono text-red-400">{validationError}</p>
        </div>
      )}

      {warning && (
        <div className="flex items-start gap-2 border border-amber-500/25 bg-amber-500/5 px-4 py-3 mb-4">
          <AlertTriangle className="w-3.5 h-3.5 text-amber-400 shrink-0 mt-0.5" />
          <p className="text-xs font-mono text-amber-400">
            Your choices are non-monotone (you switched back from B to A). This is allowed but unusual — please verify your intent before submitting.
          </p>
        </div>
      )}

      <button
        onClick={handleSubmit}
        className="w-full py-3.5 bg-foreground text-background text-xs font-mono uppercase tracking-[0.2em] hover:opacity-90 transition-opacity"
      >
        Submit and Enter Lobby
      </button>
    </FlowShell>
  );
}
