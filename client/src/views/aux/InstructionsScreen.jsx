import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { apiGet, apiPost } from "../../lib/api";
import { FlowShell } from "../../components/FlowShell";
import { ChevronRight } from "lucide-react";
import InstructionsScreenPreview from "./InstructionsScreen.preview";

export default function InstructionsScreen() {
  const navigate = useNavigate();
  const [showTournamentPayoutScreen, setShowTournamentPayoutScreen] = useState(true);

  useEffect(() => {
    let active = true;
    apiGet("/state")
      .then((state) => {
        if (!active) return;
        setShowTournamentPayoutScreen(state.show_tournament_payout_screen !== false);
      })
      .catch(() => {});
    return () => {
      active = false;
    };
  }, []);

  async function goQuiz() {
    await apiPost("/flow_step", { flow_step: "quiz" });
    navigate("/quiz");
  }

  return (
    <FlowShell step={2} total={5} title="How the Market Works">
      <div className="space-y-5 mb-8">
        <div className="border border-border p-4">
          <p className="text-sm font-mono text-foreground mb-2">1. What you'll do</p>
          <p className="text-sm leading-relaxed text-foreground/75" style={{ fontFamily: "Spectral, Georgia, serif" }}>
            You will trade in four markets. Each market has five rounds, and each round lasts 90 seconds.
          </p>
        </div>

        <div className="border border-border p-4">
          <p className="text-sm font-mono text-foreground mb-2">2. How prices work (LMSR)</p>
          <p className="text-sm leading-relaxed text-foreground/75" style={{ fontFamily: "Spectral, Georgia, serif" }}>
            Prices use an LMSR market maker with b = 30. Every trade moves the displayed probability. Buying YES pushes YES up; buying NO pushes YES down.
          </p>
        </div>

        <div className="border border-border p-4">
          <p className="text-sm font-mono text-foreground mb-2">3. Your role</p>
          <p className="text-sm leading-relaxed text-foreground/75" style={{ fontFamily: "Spectral, Georgia, serif" }}>
            Participants are either informed or uninformed. Informed participants receive a private signal each round. Uninformed participants only receive public bulletins.
          </p>
        </div>

        <div className="border border-border p-4">
          <p className="text-sm font-mono text-foreground mb-3">4. Trading screen tour</p>
          <InstructionsScreenPreview />
        </div>

        {showTournamentPayoutScreen && (
          <div className="border border-border p-4">
            <p className="text-sm font-mono text-foreground mb-2">5. Tournament and payouts</p>
            <p className="text-sm leading-relaxed text-foreground/75" style={{ fontFamily: "Spectral, Georgia, serif" }}>
              Final ranking is based on total token balances across all markets. Top prizes are: rank 1 = 5 EUR, rank 2 = 3 EUR, rank 3 = 2 EUR.
            </p>
          </div>
        )}
      </div>

      <div className="border-t border-border pt-5">
        <button
          onClick={goQuiz}
          className="w-full py-3.5 bg-foreground text-background text-xs font-mono uppercase tracking-[0.2em] hover:opacity-90 transition-colors flex items-center justify-center gap-2"
        >
          Continue to Comprehension Quiz <ChevronRight className="w-3.5 h-3.5" />
        </button>
      </div>
    </FlowShell>
  );
}
