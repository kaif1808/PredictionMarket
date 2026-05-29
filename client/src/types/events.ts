export type RoleTier = "uninformed" | "informed";

export interface PrimingSource {
  source_type: string;
  name: string;
  tier: "public" | "analytical" | "intelligence";
  lean: "yes" | "no" | "neutral";
  text: string;
}

export interface PrimingBulletin {
  headline: string;
  sources: PrimingSource[];
}

export interface BulletinPayload {
  public: string;
  analytical: string | null;
  intelligence: string | null;
}

export interface RoundStartedEvent {
  round_number: number;
  is_practice_round: boolean;
  round_duration_seconds: number;
  trading_open: boolean;
  current_price: number;
  balance: number;
  yes_held: number;
  no_held: number;
  yes_avg_cost: number | null;
  no_avg_cost: number | null;
  bulletin: BulletinPayload;
  signal_value: "H" | "L" | null;
  signal_theta: number | null;
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

export interface RoundEndedEvent {
  round_number: number;
  closing_price: number;
  round_volume: number;
}

export interface ErrorEvent {
  code: string;
  message: string;
}

export interface ParticipantState {
  session_id: number;
  participant_id: string;
  flow_step: string | null;
  phase: string;
  show_tournament_payout_screen: boolean;
  current_market_number: number | null;
  current_round_number: number | null;
  role_tier: RoleTier | null;
  balance: number | null;
  yes_held: number | null;
  no_held: number | null;
  yes_avg_cost: number | null;
  no_avg_cost: number | null;
  current_price: number;
  bulletin: BulletinPayload | null;
  signal_value: "H" | "L" | null;
  signal_theta: number | null;
  is_practice_round: boolean;
  round_duration_seconds: number | null;
  round_deadline_unix_ms: number | null;
  priming: PrimingBulletin | null;
}

export interface ServerToClientEvents {
  state_sync: (payload: ParticipantState) => void;
  market_started: (payload: {
    market_number: number;
    is_practice: boolean;
    stage: number;
    scenario_description: string;
    role_tier: RoleTier;
    endowment_tokens: number;
    starting_balance: number;
    current_price: number;
    max_rounds: number;
    priming: PrimingBulletin | null;
  }) => void;
  round_started: (payload: RoundStartedEvent) => void;
  price_update: (payload: PriceUpdateEvent) => void;
  round_ended: (payload: RoundEndedEvent) => void;
  market_outcome_public: (payload: MarketOutcomePublicEvent) => void;
  market_resolved: (payload: MarketResolvedEvent) => void;
  session_closed: (payload: { session_id: number }) => void;
  error: (payload: ErrorEvent) => void;
}
