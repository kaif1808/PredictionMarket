import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiPost } from "../../lib/api";
import { FlowShell } from "../../components/FlowShell";
import { AlertTriangle, X, CheckCircle } from "lucide-react";

const QUESTIONS = [
  {
    id: "q1",
    prompt: "Can you submit a trade larger than your current token balance?",
    options: ["Yes", "No"],
    answer: "No",
  },
  {
    id: "q2",
    prompt: "Do uninformed participants receive a private signal each round?",
    options: ["Yes", "No"],
    answer: "No",
  },
  {
    id: "q3",
    prompt: "How many market stages are in one full session?",
    options: ["2", "3", "4"],
    answer: "4",
  },
  {
    id: "q4",
    prompt: "Who can see interim tournament rankings during the session?",
    options: ["Everyone", "Only admin", "Only top 3 participants"],
    answer: "Only admin",
  },
  {
    id: "q5",
    prompt: "When is final ranking shown to participants?",
    options: ["Every round", "Only debrief", "Never"],
    answer: "Only debrief",
  },
];

export default function ComprehensionQuizScreen() {
  const navigate = useNavigate();
  const [answers, setAnswers] = useState(/** @type {Record<string,string>} */ ({}));
  const [attempts, setAttempts] = useState(0);
  const [wrongIds, setWrongIds] = useState(/** @type {string[]} */ ([]));
  const [submitted, setSubmitted] = useState(false);

  /** @param {React.FormEvent<HTMLFormElement>} e */
  async function handleSubmit(e) {
    e.preventDefault();
    const nextAttempts = attempts + 1;
    setAttempts(nextAttempts);
    const wrong = QUESTIONS.filter((q) => answers[q.id] !== q.answer).map((q) => q.id);
    setWrongIds(wrong);
    const correct = wrong.length === 0;
    await apiPost("/quiz/comprehension/submit", {
      attempts: nextAttempts,
      final_correct: correct,
      raw_answers: answers,
    });
    if (!correct) return;
    setSubmitted(true);
    await apiPost("/flow_step", { flow_step: "risk" });
    navigate("/risk");
  }

  if (submitted) {
    return (
      <FlowShell step={3} total={5} title="Comprehension Quiz">
        <div className="border border-green-500/25 bg-green-500/5 px-5 py-6 text-center mb-6">
          <CheckCircle className="w-6 h-6 text-green-500 mx-auto mb-3" />
          <p className="text-sm font-mono text-green-400">All answers correct.</p>
          {attempts > 1 && (
            <p className="text-[11px] font-mono text-muted-foreground mt-1">{attempts} attempts recorded.</p>
          )}
        </div>
      </FlowShell>
    );
  }

  return (
    <FlowShell step={3} total={5} title="Comprehension Quiz">
      <form onSubmit={handleSubmit} className="space-y-0">
        <p className="text-sm text-foreground/70 mb-6" style={{ fontFamily: "Spectral, Georgia, serif" }}>
          All questions must be answered correctly before you may proceed. You may retry as many times as needed.
        </p>
        {QUESTIONS.map((q, i) => {
          const isWrong = wrongIds.includes(q.id);
          return (
            <div key={q.id} className={`border-t border-border py-5 ${isWrong ? "bg-red-500/3" : ""}`}>
              <div className="flex gap-3 mb-3">
                <span className="text-[10px] font-mono text-muted-foreground tabular-nums shrink-0 mt-0.5">
                  {String(i + 1).padStart(2, "0")}
                </span>
                <p className={`text-sm ${isWrong ? "text-red-500" : "text-foreground"}`}>{q.prompt}</p>
              </div>
              <div className="flex flex-wrap gap-2 pl-8">
                {q.options.map((opt) => (
                  <label
                    key={opt}
                    className={`flex items-center gap-2 px-3 py-1.5 border cursor-pointer transition-colors text-xs font-mono ${
                      answers[q.id] === opt
                        ? "border-foreground bg-foreground/8 text-foreground"
                        : "border-border text-muted-foreground hover:border-foreground/40"
                    }`}
                  >
                    <input
                      type="radio"
                      name={q.id}
                      value={opt}
                      className="sr-only"
                      onChange={() => setAnswers((a) => ({ ...a, [q.id]: opt }))}
                    />
                    {opt}
                  </label>
                ))}
              </div>
              {isWrong && (
                <p className="text-[10px] font-mono text-red-500 pl-8 mt-2 flex items-center gap-1">
                  <X className="w-3 h-3" /> Incorrect — please review the instructions.
                </p>
              )}
            </div>
          );
        })}
        <div className="border-t border-border pt-6">
          {attempts > 0 && wrongIds.length > 0 && (
            <p className="text-xs font-mono text-red-500 mb-4 flex items-center gap-1.5">
              <AlertTriangle className="w-3 h-3" />
              {wrongIds.length} incorrect answer{wrongIds.length !== 1 ? "s" : ""} — attempt {attempts} recorded.
            </p>
          )}
          <button
            type="submit"
            className="w-full py-3.5 bg-foreground text-background text-xs font-mono uppercase tracking-[0.2em] hover:opacity-90 transition-opacity"
          >
            Submit Quiz
          </button>
        </div>
      </form>
    </FlowShell>
  );
}
