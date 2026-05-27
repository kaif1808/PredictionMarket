import { useNavigate } from "react-router-dom";
import { apiPost } from "../../lib/api";

export default function InstructionsScreen() {
  const navigate = useNavigate();

  async function goQuiz() {
    await apiPost("/flow_step", { flow_step: "quiz" });
    navigate("/quiz");
  }

  return (
    <div className="container-main">
      <div className="card">
        <h1 className="mb-3 text-2xl font-semibold">Instructions</h1>
        <ul className="mb-4 list-disc space-y-2 pl-5 text-sm text-slate-700">
          <li>You will trade YES/NO contracts across four markets.</li>
          <li>Prices update continuously based on all participants&apos; trades.</li>
          <li>Your private information varies by role and by market stage.</li>
          <li>Tournament prizes: rank 1 receives €5, rank 2 receives €3, rank 3 receives €2.</li>
        </ul>
        <button className="btn-primary" onClick={goQuiz}>
          Continue to Comprehension Quiz
        </button>
      </div>
    </div>
  );
}
