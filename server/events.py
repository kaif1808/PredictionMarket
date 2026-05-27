from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class BulletinPayload(BaseModel):
    public: str
    analytical: str | None = None
    intelligence: str | None = None


class SessionStartedEvent(BaseModel):
    session_id: int
    session_label: str


class MarketStartedEvent(BaseModel):
    market_number: int
    stage: int
    scenario_description: str
    role_tier: Literal["uninformed", "semi_informed", "insider"]
    endowment_tokens: float
    starting_balance: float
    current_price: float
    max_rounds: int = 5


class RoundStartedEvent(BaseModel):
    round_number: int
    trading_open: bool = True
    current_price: float
    balance: float
    yes_held: float
    no_held: float
    bulletin: BulletinPayload
    posterior: float | None = None
    round_deadline_unix_ms: int


class LastTradePayload(BaseModel):
    participant_id_hashed: str
    direction: Literal["yes", "no"]
    quantity: int
    price_before: float
    price_after: float


class PriceUpdateEvent(BaseModel):
    current_price: float
    q_yes: float
    q_no: float
    last_trade: LastTradePayload


class RoundEndedEvent(BaseModel):
    round_number: int
    closing_price: float
    round_volume: int


class MarketResolvedEvent(BaseModel):
    outcome: int
    outcome_label: str
    true_probability: float
    payout: float
    final_balance: float
    pnl: float


class MarketOutcomePublicEvent(BaseModel):
    outcome: int
    outcome_label: str
    true_probability: float


class ErrorEvent(BaseModel):
    code: str
    message: str


class TradeRequest(BaseModel):
    side: Literal["buy", "sell"] = "buy"
    direction: Literal["yes", "no"]
    quantity: int = Field(ge=1, le=20)
