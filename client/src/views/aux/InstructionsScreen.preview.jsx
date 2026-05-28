import { Clock, ListOrdered, Signal, TrendingUp } from "lucide-react";
import { SectionLabel } from "../../components/SectionLabel";

/**
 * @param {{ n: number; title: string; text: string }} props
 */
function Callout({ n, title, text }) {
  return (
    <div className="border border-border px-3 py-2 bg-card/40">
      <p className="text-[10px] font-mono uppercase tracking-[0.14em] text-muted-foreground mb-1">
        {n}. {title}
      </p>
      <p className="text-xs text-foreground/75" style={{ fontFamily: "Spectral, Georgia, serif" }}>
        {text}
      </p>
    </div>
  );
}

export default function InstructionsScreenPreview() {
  return (
    <div className="border border-border p-4 bg-card/20">
      <SectionLabel>Trading Screen Preview</SectionLabel>
      <div className="grid grid-cols-1 lg:grid-cols-[1fr_280px] gap-4 mb-4">
        <div className="border border-border p-4">
          <p className="text-sm text-foreground/85 mb-2" style={{ fontFamily: "Spectral, Georgia, serif" }}>
            Will Valdoria enter armed conflict with Norheim within 12 months of the Karvac incident?
          </p>
          <p className="text-3xl font-mono font-semibold mb-3">54.0%</p>
          <div className="h-24 border border-border mb-3 flex items-center justify-center text-[11px] font-mono text-muted-foreground">
            Price chart (updates live while trading)
          </div>
          <div className="space-y-2">
            <div className="border border-border p-2">
              <p className="text-[10px] font-mono uppercase tracking-[0.12em] text-muted-foreground mb-1 flex items-center gap-1">
                <Signal className="w-3 h-3" /> Private Signal
              </p>
              <p className="text-sm text-foreground/80">Your private signal this round: H (theta = 0.85)</p>
            </div>
            <div className="border border-border p-2">
              <p className="text-[10px] font-mono uppercase tracking-[0.12em] text-muted-foreground mb-1 flex items-center gap-1">
                <ListOrdered className="w-3 h-3" /> Recent Trades
              </p>
              <p className="text-[11px] font-mono text-foreground/70">Pxx bought YES x2, Pxx sold NO x1...</p>
            </div>
          </div>
        </div>
        <div className="border border-border p-4">
          <SectionLabel>Order Entry</SectionLabel>
          <div className="grid grid-cols-2 gap-2 mb-3">
            <button className="border border-border py-2 text-[10px] font-mono uppercase">Buy</button>
            <button className="border border-border py-2 text-[10px] font-mono uppercase">Sell</button>
          </div>
          <div className="grid grid-cols-2 gap-2 mb-3">
            <button className="border border-green-500/40 py-2 text-green-500 text-xs font-mono">YES</button>
            <button className="border border-red-500/40 py-2 text-red-500 text-xs font-mono">NO</button>
          </div>
          <div className="border border-border p-2 mb-3">
            <p className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Quantity</p>
            <p className="text-sm font-mono">1 contract</p>
          </div>
          <div className="border border-border p-2 mb-3">
            <p className="text-[10px] font-mono uppercase text-muted-foreground mb-1">Position</p>
            <p className="text-xs font-mono">Balance 100T · YES 0 · NO 0</p>
          </div>
          <div className="border border-border p-2">
            <p className="text-[10px] font-mono uppercase text-muted-foreground mb-1 flex items-center gap-1">
              <Clock className="w-3 h-3" /> Round Timer
            </p>
            <p className="text-sm font-mono">01:30 remaining</p>
          </div>
        </div>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-3 gap-2">
        <Callout n={1} title="Order side toggle" text="Pick Buy or Sell before placing a trade." />
        <Callout n={2} title="Quantity input" text="Enter contracts (1 to 20) for the selected side." />
        <Callout n={3} title="Position summary" text="Track balance, holdings, and average purchase cost." />
        <Callout n={4} title="Signal panel" text="Informed participants see one private signal and theta each round." />
        <Callout n={5} title="Round timer" text="Trading closes automatically at the deadline." />
        <Callout n={6} title="Recent trades" text="Observe market flow from anonymized order activity." />
      </div>
      <p className="text-[10px] font-mono text-muted-foreground mt-3 flex items-center gap-1">
        <TrendingUp className="w-3 h-3" /> Preview is static and non-interactive; the live market updates in real time.
      </p>
    </div>
  );
}
