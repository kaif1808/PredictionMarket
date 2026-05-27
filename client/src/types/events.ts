export type RoleTier = "uninformed" | "semi_informed" | "insider";

export interface BulletinPayload {
  public: string;
  analytical: string | null;
  intelligence: string | null;
}

export interface RoundStartedEvent {
  round_number: number;
  trading_open: boolean;
  current_price: number;
  balance: number;
  yes_held: number;
  no_held: number;
  bulletin: BulletinPayload;
  posterior: number | null;
  round_deadline_unix_ms: number;
}

export interface PriceUpdateEvent {
  current_price: number;
  q_yes: number;
  q_no: number;
  last_trade: {
    participant_id_hashed: string;
    direction: "yes" | "no";
    quantity: number;
    price_before: number;
    price_after: number;
  };
}

export interface MarketOutcomePublicEvent {
  outcome: 0 | 1;
  outcome_label: string;
  true_probability: number;
}

export interface MarketResolvedEvent extends MarketOutcomePublicEvent {
  payout: number;
  final_balance: number;
  pnl: number;
}
