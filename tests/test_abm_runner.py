from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from calibration.abm.config import SimConfig
from calibration.abm.runner import _build_session_factory, run_abm
from server.db_models import Market, MarketResolution, MarketRole, Round, Signal, TournamentRanking, Trade


def test_abm_runner_writes_full_real_session(tmp_path) -> None:
    db_path = tmp_path / "abm_runner.db"
    config = SimConfig(
        seed=7,
        subject_count=9,
        treated_count=3,
        b=18.0,
        num_sessions=1,
        include_practice=True,
        db_path=str(db_path),
        outdir=tmp_path / "out",
    )
    result = run_abm(config)
    assert len(result.session_ids) == 1
    sid = result.session_ids[0]

    db_factory: sessionmaker = _build_session_factory(result.database_url)
    with db_factory() as db:
        non_practice_markets = db.scalars(
            select(Market).where(Market.session_id == sid, Market.is_practice.is_(False)).order_by(Market.market_number)
        ).all()
        assert len(non_practice_markets) == 4
        assert [m.market_number for m in non_practice_markets] == [1, 2, 3, 4]

        rounds_count = db.scalar(
            select(func.count(Round.id))
            .join(Market, Round.market_id == Market.id)
            .where(Market.session_id == sid, Market.is_practice.is_(False))
        )
        assert rounds_count == 20

        practice_markets = db.scalars(select(Market).where(Market.session_id == sid, Market.is_practice.is_(True))).all()
        assert len(practice_markets) == 1

        signal_counts = dict(
            db.execute(
                select(Market.market_number, func.count(Signal.id))
                .join(Round, Round.market_id == Market.id)
                .join(Signal, Signal.round_id == Round.id)
                .where(Market.session_id == sid)
                .group_by(Market.market_number)
            ).all()
        )
        assert signal_counts[0] == 9
        assert signal_counts[1] == 45
        assert signal_counts[2] == 15
        assert 3 not in signal_counts
        assert signal_counts[4] == 15

        delivered_false_stage1 = db.scalar(
            select(func.count(Signal.id))
            .join(Round, Signal.round_id == Round.id)
            .join(Market, Round.market_id == Market.id)
            .where(Market.session_id == sid, Market.stage == 1, Signal.delivered.is_(False))
        )
        assert delivered_false_stage1 == 54

        trades = db.scalars(
            select(Trade)
            .join(Round, Trade.round_id == Round.id)
            .join(Market, Round.market_id == Market.id)
            .where(Market.session_id == sid, Market.is_practice.is_(False))
        ).all()
        assert trades
        assert all(t.quantity <= 20 for t in trades)
        assert all(float(t.cost) >= 0 for t in trades)

        roles = db.scalars(select(MarketRole).join(Market, MarketRole.market_id == Market.id).where(Market.session_id == sid)).all()
        assert all(float(r.starting_balance) >= 0 for r in roles)
        assert all(float(r.yes_held) >= 0 and float(r.no_held) >= 0 for r in roles)

        resolutions = db.scalars(
            select(MarketResolution).join(Market, MarketResolution.market_id == Market.id).where(Market.session_id == sid)
        ).all()
        assert len(resolutions) == 4

        rankings = db.scalars(select(TournamentRanking).where(TournamentRanking.session_id == sid)).all()
        assert len(rankings) == 9
