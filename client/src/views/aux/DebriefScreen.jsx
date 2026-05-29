import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../../lib/api";
import { SectionLabel } from "../../components/SectionLabel";
import { Award, CheckCircle } from "lucide-react";

const DEBRIEF_QUESTIONS = [
  {
    id: "experimental_economics",
    prompt: "Did you know anything about experimental economics before this session?",
  },
  {
    id: "prediction_market_literature",
    prompt: "Were you familiar with the literature around prediction markets before today?",
  },
  {
    id: "prediction_market_use",
    prompt: "Had you ever used a prediction market such as Polymarket or Kalshi before this study?",
  },
];

export default function DebriefScreen() {
  const [strategy, setStrategy] = useState("");
  const [quizAnswers, setQuizAnswers] = useState(/** @type {Record<string, string>} */ ({}));
  const [submitted, setSubmitted] = useState(false);
  const [tournament, setTournament] = useState(/** @type {{ rank: number; total_tokens: number; prize_eur: number } | null} */ (null));
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet("/tournament/final")
      .then(setTournament)
      .catch(() => setTournament(null));
  }, []);

  async function submit() {
    const unanswered = DEBRIEF_QUESTIONS.filter((q) => !quizAnswers[q.id]);
    if (unanswered.length > 0) {
      setError("Please answer all background questions before submitting.");
      return;
    }
    try {
      await apiPost("/debrief/submit", { answers: { strategy, ...quizAnswers } });
      setSubmitted(true);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit debrief");
    }
  }

  return (
    <div className="min-h-screen flex flex-col items-center justify-center px-6 py-16">
      <div className="w-full max-w-xl space-y-8">
        {/* Header */}
        <div className="text-center">
          <p className="text-[10px] font-mono uppercase tracking-[0.3em] text-muted-foreground mb-3">
            Session Complete
          </p>
          <h1 className="text-3xl font-light" style={{ fontFamily: "Spectral, Georgia, serif" }}>
            Session Debrief
          </h1>
          <div className="w-8 h-px bg-border mx-auto mt-4" />
        </div>

        {/* Tournament result */}
        {tournament ? (
          <div>
            <SectionLabel>Your Tournament Result</SectionLabel>
            <div className="border border-border overflow-hidden">
              <div className="grid grid-cols-[2rem_1fr_1fr_1fr] border-b border-border bg-card/60">
                {["Rank", "Tokens", "Prize", ""].map((h, i) => (
                  <div key={i} className="px-4 py-2 text-[9px] font-mono uppercase tracking-[0.15em] text-muted-foreground border-r border-border last:border-r-0">
                    {h}
                  </div>
                ))}
              </div>
              <div className={`grid grid-cols-[2rem_1fr_1fr_1fr] ${tournament.rank <= 3 ? "bg-amber-500/5" : ""}`}>
                <div className="px-4 py-3 text-[11px] font-mono tabular-nums text-muted-foreground border-r border-border flex items-center gap-1.5">
                  {tournament.rank <= 3 ? (
                    <Award className={`w-3 h-3 ${tournament.rank === 1 ? "text-amber-400" : tournament.rank === 2 ? "text-slate-400" : "text-amber-700"}`} />
                  ) : tournament.rank}
                </div>
                <div className="px-4 py-3 text-[11px] font-mono tabular-nums text-foreground border-r border-border">
                  {Number(tournament.total_tokens).toFixed(1)} T
                </div>
                <div className={`px-4 py-3 text-[11px] font-mono tabular-nums border-r border-border ${tournament.prize_eur > 0 ? "text-green-500" : "text-muted-foreground"}`}>
                  {tournament.prize_eur > 0 ? `€${Number(tournament.prize_eur).toFixed(2)}` : "—"}
                </div>
                <div className="px-4 py-3 text-[11px] font-mono text-muted-foreground">
                  Rank {tournament.rank}
                </div>
              </div>
            </div>
          </div>
        ) : (
          <p className="text-sm font-mono text-muted-foreground">
            Tournament ranking will appear after session closure.
          </p>
        )}

        {/* Strategy feedback */}
        <div>
          <SectionLabel>Strategy & Feedback</SectionLabel>
          {submitted ? (
            <div className="border border-green-500/25 bg-green-500/5 px-5 py-4 flex items-center gap-3">
              <CheckCircle className="w-4 h-4 text-green-500 shrink-0" />
              <p className="text-sm font-mono text-green-400">Debrief submitted. Thank you for participating.</p>
            </div>
          ) : (
            <div className="space-y-3">
              <textarea
                value={strategy}
                onChange={(e) => {
                  setStrategy(e.target.value);
                  setError("");
                }}
                placeholder="Describe how you made trading decisions — what information did you rely on, what signals guided your choices?"
                className="w-full h-32 bg-transparent border border-border px-4 py-3 text-sm text-foreground/85 placeholder:text-muted-foreground/50 focus:outline-none focus:border-foreground/50 resize-none transition-colors"
                style={{ fontFamily: "Spectral, Georgia, serif" }}
              />
              <div className="border border-border p-4 space-y-4">
                <p className="text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground">
                  Background quiz
                </p>
                {DEBRIEF_QUESTIONS.map((q) => (
                  <div key={q.id} className="space-y-2">
                    <p className="text-sm text-foreground/80" style={{ fontFamily: "Spectral, Georgia, serif" }}>
                      {q.prompt}
                    </p>
                    <div className="flex gap-2">
                      {[
                        { label: "Yes", value: "yes" },
                        { label: "No", value: "no" },
                      ].map((opt) => (
                        <label
                          key={opt.value}
                          className={`flex items-center gap-2 px-3 py-1.5 border cursor-pointer transition-colors text-xs font-mono ${
                            quizAnswers[q.id] === opt.value
                              ? "border-foreground bg-foreground/8 text-foreground"
                              : "border-border text-muted-foreground hover:border-foreground/40"
                          }`}
                        >
                          <input
                            type="radio"
                            name={q.id}
                            value={opt.value}
                            className="sr-only"
                            onChange={() => {
                              setQuizAnswers((a) => ({ ...a, [q.id]: opt.value }));
                              setError("");
                            }}
                          />
                          {opt.label}
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
              <button
                onClick={submit}
                className="w-full py-3.5 bg-foreground text-background text-xs font-mono uppercase tracking-[0.2em] hover:opacity-90 transition-opacity"
              >
                Submit Debrief
              </button>
              {error && (
                <p className="text-xs font-mono text-red-500">{error}</p>
              )}
            </div>
          )}
        </div>

        <p className="text-center text-[10px] font-mono text-muted-foreground">
          You may close this window. Payment will be arranged by the experimenter.
        </p>
      </div>
    </div>
  );
}
