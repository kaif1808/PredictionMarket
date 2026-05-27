import { useNavigate } from "react-router-dom";
import { apiPost } from "../../lib/api";
import { FlowShell } from "../../components/FlowShell";
import { ChevronRight } from "lucide-react";

export default function InstructionsScreen() {
  const navigate = useNavigate();

  async function goQuiz() {
    await apiPost("/flow_step", { flow_step: "quiz" });
    navigate("/quiz");
  }

  const bullets = [
    {
      heading: "Four markets, five rounds each",
      body: "You will trade across four independent markets. Each market runs five 90-second trading rounds on the same underlying question.",
    },
    {
      heading: "LMSR pricing — every trade moves the price",
      body: "The market uses a Logarithmic Market Scoring Rule (B = 30). Buying YES contracts raises the YES probability; buying NO lowers it. Your cost depends on how much you move the price.",
    },
    {
      heading: "Your information depends on your role",
      body: "Uninformed participants receive only public bulletins. Semi-informed and insider participants additionally receive a private posterior probability derived from a signal with known reliability.",
    },
    {
      heading: "Tournament incentives",
      body: "Final token balances across all markets determine your rank. Top three participants receive cash prizes: €5 (rank 1), €3 (rank 2), €2 (rank 3). Rankings are revealed only at debrief.",
    },
  ];

  return (
    <FlowShell step={2} total={5} title="How the Market Works">
      <div className="space-y-0 mb-8">
        {bullets.map(({ heading, body }, i) => (
          <div key={heading} className="border-t border-border py-4 flex gap-4">
            <span className="text-[10px] font-mono text-muted-foreground tabular-nums shrink-0 mt-0.5 w-5">
              {String(i + 1).padStart(2, "0")}
            </span>
            <div>
              <p className="text-sm font-mono text-foreground mb-1.5">{heading}</p>
              <p className="text-sm leading-relaxed text-foreground/75" style={{ fontFamily: "Spectral, Georgia, serif" }}>
                {body}
              </p>
            </div>
          </div>
        ))}
        <div className="border-t border-border" />
      </div>
      <button
        onClick={goQuiz}
        className="w-full py-3.5 bg-foreground text-background text-xs font-mono uppercase tracking-[0.2em] hover:opacity-90 transition-colors flex items-center justify-center gap-2"
      >
        Continue to Comprehension Quiz <ChevronRight className="w-3.5 h-3.5" />
      </button>
    </FlowShell>
  );
}
