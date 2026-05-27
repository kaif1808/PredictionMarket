import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiPost } from "../../lib/api";

const ROWS = Array.from({ length: 10 }, (_, i) => i + 1);

export default function HoltLauryScreen() {
  const navigate = useNavigate();
  const [choices, setChoices] = useState(() => Object.fromEntries(ROWS.map((n) => [n, "A"])));
  const [warning, setWarning] = useState("");

  const switchPoint = useMemo(() => {
    for (const n of ROWS) {
      if (choices[n] === "B") return n;
    }
    return null;
  }, [choices]);

  function isMonotone() {
    let sawB = false;
    for (const n of ROWS) {
      if (choices[n] === "B") sawB = true;
      if (sawB && choices[n] === "A") return false;
    }
    return true;
  }

  async function submit() {
    const monotone = isMonotone();
    if (!monotone) {
      setWarning("Choices are non-monotone. Submission is allowed but please verify intent.");
    } else {
      setWarning("");
    }
    await apiPost("/risk_elicitation/submit", {
      instrument: "holt_laury_10",
      switch_point: switchPoint,
      raw_choices: choices
    });
    navigate("/lobby");
  }

  return (
    <div className="container-main">
      <div className="card">
        <h1 className="mb-3 text-2xl font-semibold">Risk Elicitation (Holt-Laury)</h1>
        <p className="mb-4 text-sm text-slate-700">
          Choose Option A or B in each row. Option B is riskier.
        </p>
        <div className="space-y-2">
          {ROWS.map((n) => (
            <div key={n} className="flex items-center justify-between rounded border border-slate-200 p-2">
              <span className="text-sm">Row {n}</span>
              <div className="flex gap-4 text-sm">
                <label>
                  <input
                    type="radio"
                    name={`row-${n}`}
                    checked={choices[n] === "A"}
                    onChange={() => setChoices((prev) => ({ ...prev, [n]: "A" }))}
                  />{" "}
                  A
                </label>
                <label>
                  <input
                    type="radio"
                    name={`row-${n}`}
                    checked={choices[n] === "B"}
                    onChange={() => setChoices((prev) => ({ ...prev, [n]: "B" }))}
                  />{" "}
                  B
                </label>
              </div>
            </div>
          ))}
        </div>
        <button className="btn-primary mt-4" onClick={submit}>
          Submit and Enter Lobby
        </button>
        {warning ? <p className="mt-3 text-sm text-amber-700">{warning}</p> : null}
      </div>
    </div>
  );
}
