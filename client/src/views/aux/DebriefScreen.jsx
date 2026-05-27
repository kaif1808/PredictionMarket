import { useEffect, useState } from "react";
import { apiGet, apiPost } from "../../lib/api";

/**
 * @typedef {object} TournamentFinal
 * @property {number} rank
 * @property {number} total_tokens
 * @property {number} prize_eur
 */

export default function DebriefScreen() {
  const [strategy, setStrategy] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [tournament, setTournament] = useState(/** @type {TournamentFinal | null} */ (null));
  const [error, setError] = useState("");

  useEffect(() => {
    apiGet("/tournament/final")
      .then(setTournament)
      .catch(() => setTournament(null));
  }, []);

  async function submit() {
    try {
      await apiPost("/debrief/submit", { answers: { strategy } });
      setSubmitted(true);
      setError("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to submit debrief");
    }
  }

  return (
    <div className="container-main">
      <div className="card">
        <h1 className="mb-2 text-2xl font-semibold">Debrief</h1>
        <p className="mb-4 text-sm text-slate-700">Share your strategy and feedback.</p>
        <textarea
          className="mb-3 h-28 w-full rounded border border-slate-300 p-2"
          placeholder="How did you make trading decisions?"
          value={strategy}
          onChange={(e) => setStrategy(e.target.value)}
        />
        <button className="btn-primary" onClick={submit}>
          Submit Debrief
        </button>
        {submitted ? <p className="mt-3 text-sm text-green-700">Debrief submitted.</p> : null}
        {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}

        {tournament ? (
          <div className="mt-6 rounded border border-cyan-200 bg-cyan-50 p-3 text-sm">
            <p className="font-medium">Final tournament result</p>
            <p>Rank: {tournament.rank}</p>
            <p>Total tokens: {tournament.total_tokens}</p>
            <p>Prize: €{tournament.prize_eur}</p>
          </div>
        ) : (
          <p className="mt-6 text-sm text-slate-600">Tournament ranking will appear after session closure.</p>
        )}
      </div>
    </div>
  );
}
