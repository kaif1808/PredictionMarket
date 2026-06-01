from __future__ import annotations

from sqlalchemy import func, select

from calibration.abm.config import SimConfig
from calibration.abm.runner import _build_session_factory, run_abm
from server.db_models import Market, MarketResolution, MarketRole, Round, Trade


def _golden_snapshot(tmp_path):
    config = SimConfig(
        rotation_id=1,
        subject_count=9,
        treated_count=3,
        b=18.0,
        seed=42,
        profile_mix="rational:5,herder:2,noise:2",
        num_sessions=1,
        include_practice=True,
        db_path=str(tmp_path / "abm_golden.db"),
        outdir=tmp_path / "out",
    )
    result = run_abm(config)
    sid = result.session_ids[0]
    db_factory = _build_session_factory(result.database_url)
    with db_factory() as db:
        outcomes = dict(
            db.execute(
                select(Market.market_number, MarketResolution.outcome)
                .join(MarketResolution, MarketResolution.market_id == Market.id)
                .where(Market.session_id == sid, Market.is_practice.is_(False))
                .order_by(Market.market_number)
            ).all()
        )
        closing = dict(
            db.execute(
                select(Market.market_number, Round.closing_price)
                .join(Round, Round.market_id == Market.id)
                .where(Market.session_id == sid, Market.is_practice.is_(False), Round.round_number == 5)
                .order_by(Market.market_number)
            ).all()
        )
        trade_count = db.scalar(
            select(func.count(Trade.id))
            .join(Round, Trade.round_id == Round.id)
            .join(Market, Round.market_id == Market.id)
            .where(Market.session_id == sid, Market.is_practice.is_(False))
        )
        returns = db.execute(
            select(
                MarketRole.role_tier,
                func.avg((MarketRole.final_balance - MarketRole.endowment_tokens) / MarketRole.endowment_tokens),
            )
            .join(Market, MarketRole.market_id == Market.id)
            .where(Market.session_id == sid, Market.is_practice.is_(False))
            .group_by(MarketRole.role_tier)
        ).all()
    return outcomes, closing, int(trade_count or 0), {k: float(v) for k, v in returns}


def test_abm_golden_determinism(tmp_path) -> None:
    outcomes, closing, trade_count, returns = _golden_snapshot(tmp_path)
    assert outcomes == {1: 1, 2: 0, 3: 0, 4: 1}
    assert {k: round(float(v), 6) for k, v in closing.items()} == {
        1: 0.500000,
        2: 0.782071,
        3: 0.500000,
        4: 0.158869,
    }
    assert trade_count == 158
    assert round(returns["informed"], 6) == -0.359282
    assert round(returns["uninformed"], 6) == 0.203350
    assert trade_count > 0
