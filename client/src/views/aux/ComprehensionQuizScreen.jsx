import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useForm } from "react-hook-form";
import { apiPost } from "../../lib/api";

const QUESTIONS = [
  {
    id: "q1",
    prompt: "Can you submit a trade larger than your current token balance?",
    options: ["Yes", "No"],
    answer: "No"
  },
  {
    id: "q2",
    prompt: "Do uninformed participants receive a private posterior value?",
    options: ["Yes", "No"],
    answer: "No"
  },
  {
    id: "q3",
    prompt: "How many market stages are in one full session?",
    options: ["2", "3", "4"],
    answer: "4"
  },
  {
    id: "q4",
    prompt: "Who can see interim tournament rankings during the session?",
    options: ["Everyone", "Only admin", "Only top 3 participants"],
    answer: "Only admin"
  },
  {
    id: "q5",
    prompt: "When is final ranking shown to participants?",
    options: ["Every round", "Only debrief", "Never"],
    answer: "Only debrief"
  }
];

export default function ComprehensionQuizScreen() {
  const navigate = useNavigate();
  const [attempts, setAttempts] = useState(0);
  const [error, setError] = useState("");
  const { register, handleSubmit } = useForm();

  const answers = useMemo(
    () => Object.fromEntries(QUESTIONS.map((q) => [q.id, q.answer])),
    []
  );

  async function onSubmit(values) {
    const nextAttempts = attempts + 1;
    setAttempts(nextAttempts);
    const correct = QUESTIONS.every((q) => values[q.id] === answers[q.id]);
    await apiPost("/quiz/comprehension/submit", {
      attempts: nextAttempts,
      final_correct: correct,
      raw_answers: values
    });
    if (!correct) {
      setError("Some answers are incorrect. Please review and try again.");
      return;
    }
    await apiPost("/flow_step", { flow_step: "risk" });
    navigate("/risk");
  }

  return (
    <div className="container-main">
      <form className="card space-y-4" onSubmit={handleSubmit(onSubmit)}>
        <h1 className="text-2xl font-semibold">Comprehension Quiz</h1>
        <p className="text-sm text-slate-700">You must answer all questions correctly to continue.</p>
        {QUESTIONS.map((q) => (
          <div key={q.id}>
            <p className="mb-2 text-sm font-medium">{q.prompt}</p>
            <div className="space-y-1">
              {q.options.map((opt) => (
                <label className="block text-sm" key={opt}>
                  <input
                    className="mr-2"
                    type="radio"
                    value={opt}
                    {...register(q.id, { required: true })}
                  />
                  {opt}
                </label>
              ))}
            </div>
          </div>
        ))}
        <button type="submit" className="btn-primary">
          Submit Quiz
        </button>
        {error ? <p className="text-sm text-red-700">{error}</p> : null}
      </form>
    </div>
  );
}
