import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiPost } from "../../lib/api";
import { FlowShell } from "../../components/FlowShell";
import { AlertTriangle, CheckCircle } from "lucide-react";

export default function ConsentScreen() {
  const navigate = useNavigate();
  const [consented, setConsented] = useState(false);
  const [fakeName, setFakeName] = useState("");
  const [error, setError] = useState("");

  /** @param {React.FormEvent<HTMLFormElement>} e */
  async function onContinue(e) {
    e.preventDefault();
    if (!consented || !fakeName.trim()) {
      setError("Consent and fake name are required.");
      return;
    }
    setError("");
    await apiPost("/flow_step", { flow_step: "instructions", metadata: { consented: true, name: fakeName } });
    navigate("/instructions");
  }

  return (
    <FlowShell step={1} total={5} title="Participant Consent">
      <form onSubmit={onContinue} className="space-y-6">
        <div
          className="border border-border bg-card/50 px-5 py-4 space-y-3 text-sm leading-relaxed text-foreground/80"
          style={{ fontFamily: "Spectral, Georgia, serif" }}
        >
          <p>You are invited to participate in a decision-making study involving prediction-market trading decisions conducted for academic research purposes.</p>
          <p>Your participation is voluntary. All responses will be anonymised. Session data is stored securely and used solely for research analysis.</p>
          <p>The session will last approximately 60–90 minutes. You may withdraw at any time without penalty.</p>
          <p>Tournament incentives: final top-3 participants by total tokens receive prizes (€5, €3, €2). Prize payment is processed manually after session closure.</p>
        </div>

        <div>
          <label className="block text-[10px] font-mono uppercase tracking-[0.15em] text-muted-foreground mb-2">
            Fake name
          </label>
          <input
            value={fakeName}
            onChange={(e) => { setFakeName(e.target.value); setError(""); }}
            placeholder="Choose any alias you want"
            className="w-full bg-transparent border-b border-border px-0 py-2 text-sm font-mono focus:outline-none focus:border-foreground/60 placeholder:text-muted-foreground/50 transition-colors"
          />
        </div>

        <label className="flex items-start gap-3 cursor-pointer group">
          <div
            onClick={() => { setConsented((c) => !c); setError(""); }}
            className={`mt-0.5 w-4 h-4 border flex items-center justify-center shrink-0 transition-colors ${
              consented ? "border-foreground bg-foreground" : "border-border group-hover:border-foreground/50"
            }`}
          >
            {consented && <CheckCircle className="w-3 h-3 text-background" />}
          </div>
          <span className="text-sm text-foreground/80 leading-snug">
            I have read the study description above, I understand my participation is voluntary, and I consent to participate in this research session.
          </span>
        </label>

        {error && (
          <p className="text-xs font-mono text-red-500 flex items-center gap-1.5">
            <AlertTriangle className="w-3 h-3" /> {error}
          </p>
        )}

        <button
          type="submit"
          className="w-full py-3.5 bg-foreground text-background text-xs font-mono uppercase tracking-[0.2em] hover:opacity-90 transition-opacity"
        >
          I Consent — Continue to Instructions
        </button>
      </form>
    </FlowShell>
  );
}
