import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiPost } from "../../lib/api";

export default function ConsentScreen() {
  const navigate = useNavigate();
  const [consented, setConsented] = useState(false);
  const [name, setName] = useState("");
  const [error, setError] = useState("");

  async function onContinue(e) {
    e.preventDefault();
    if (!consented || !name.trim()) {
      setError("Consent and name are required.");
      return;
    }
    setError("");
    await apiPost("/flow_step", { flow_step: "instructions", metadata: { consented: true, name } });
    navigate("/instructions");
  }

  return (
    <div className="container-main">
      <form className="card" onSubmit={onContinue}>
        <h1 className="mb-2 text-2xl font-semibold">Consent</h1>
        <p className="mb-4 text-sm text-slate-700">
          You are invited to participate in a decision-making study involving prediction-market
          trading decisions.
        </p>
        <label className="mb-2 block text-sm">Full name</label>
        <input
          className="mb-4 w-full rounded border border-slate-300 px-3 py-2"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <label className="mb-4 flex items-start gap-2 text-sm">
          <input
            type="checkbox"
            className="mt-1"
            checked={consented}
            onChange={(e) => setConsented(e.target.checked)}
          />
          I consent to participate and understand this study is for research purposes.
        </label>
        <button type="submit" className="btn-primary">
          Continue to Instructions
        </button>
        {error ? <p className="mt-3 text-sm text-red-700">{error}</p> : null}
      </form>
    </div>
  );
}
