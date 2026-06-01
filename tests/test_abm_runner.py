from __future__ import annotations

from collections import defaultdict

from sqlalchemy import func, select
from sqlalchemy.orm import sessionmaker

from calibration.abm.config import SimConfig, preset_config
from calibration.abm.runner import _build_session_factory, _state_intensity, _update_ema_abs_return, run_abm
from server.db_models import Market, MarketResolution, MarketRole, Round, Signal, TournamentRanking, Trade


def _assert_session_integrity(*, sid: int, db_factory: sessionmaker) -> None:
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
        assert signal_counts[0] > 0
        assert signal_counts[1] > 0
        assert signal_counts[2] > 0
        assert signal_counts[4] > 0

        delivered_false_stage1 = db.scalar(
            select(func.count(Signal.id))
            .join(Round, Signal.round_id == Round.id)
            .join(Market, Round.market_id == Market.id)
            .where(Market.session_id == sid, Market.stage == 1, Signal.delivered.is_(False))
        )
        assert delivered_false_stage1 and delivered_false_stage1 > 0

        trades = db.scalars(
            select(Trade)
            .join(Round, Trade.round_id == Round.id)
            .join(Market, Round.market_id == Market.id)
            .where(Market.session_id == sid, Market.is_practice.is_(False))
            .order_by(Trade.id)
        ).all()
        assert trades
        assert all(1 <= t.quantity <= 20 for t in trades)
        assert any(float(t.cost) > 0 for t in trades)
        assert any(float(t.cost) < 0 for t in trades)

        # Virtual timestamps should be monotonic inside each round.
        by_round: dict[int, list] = defaultdict(list)
        for trade in trades:
            by_round[int(trade.round_id)].append(trade.executed_at)
        for stamps in by_round.values():
            assert stamps == sorted(stamps)

        roles = db.scalars(select(MarketRole).join(Market, MarketRole.market_id == Market.id).where(Market.session_id == sid)).all()
        assert all(float(r.starting_balance) >= 0 for r in roles)
        assert all(float(r.yes_held) >= 0 and float(r.no_held) >= 0 for r in roles)

        activity = dict(
            db.execute(
                select(Market.market_number, func.count(Trade.id))
                .join(Round, Round.market_id == Market.id)
                .join(Trade, Trade.round_id == Round.id)
                .where(Market.session_id == sid, Market.is_practice.is_(False))
                .group_by(Market.market_number)
            ).all()
        )
        assert set(activity.keys()) == {1, 2, 3, 4}
        assert all(count > 0 for count in activity.values())

        resolutions = db.scalars(
            select(MarketResolution).join(Market, MarketResolution.market_id == Market.id).where(Market.session_id == sid)
        ).all()
        assert len(resolutions) == 4

        rankings = db.scalars(select(TournamentRanking).where(TournamentRanking.session_id == sid)).all()
        participants = db.scalar(
            select(func.count(MarketRole.participant_id.distinct()))
            .join(Market, MarketRole.market_id == Market.id)
            .where(Market.session_id == sid, Market.is_practice.is_(False))
        )
        assert len(rankings) == int(participants)


def test_abm_runner_validation_config(tmp_path) -> None:
    config = preset_config("validation")
    config = SimConfig(
        **{**config.__dict__, "seed": 11, "num_sessions": 1, "include_practice": True, "db_path": str(tmp_path / "abm_v.db"), "outdir": tmp_path / "out_v"}
    )
    result = run_abm(config)
    assert len(result.session_ids) == 1
    db_factory: sessionmaker = _build_session_factory(result.database_url)
    _assert_session_integrity(sid=result.session_ids[0], db_factory=db_factory)


def test_abm_runner_production_config(tmp_path) -> None:
    config = preset_config("production")
    config = SimConfig(
        **{**config.__dict__, "seed": 17, "num_sessions": 1, "include_practice": True, "db_path": str(tmp_path / "abm_p.db"), "outdir": tmp_path / "out_p"}
    )
    result = run_abm(config)
    assert len(result.session_ids) == 1
    db_factory: sessionmaker = _build_session_factory(result.database_url)
    _assert_session_integrity(sid=result.session_ids[0], db_factory=db_factory)


def test_state_intensity_bounds_and_monotonicity() -> None:
    cfg = SimConfig().validated()
    baseline = _state_intensity(config=cfg, belief=0.5, current_price=0.5, ema_abs_return=0.0)
    higher_edge = _state_intensity(config=cfg, belief=0.95, current_price=0.5, ema_abs_return=0.0)
    higher_vol = _state_intensity(config=cfg, belief=0.5, current_price=0.5, ema_abs_return=cfg.vol_ref)
    both_high = _state_intensity(config=cfg, belief=0.95, current_price=0.5, ema_abs_return=cfg.vol_ref)

    assert cfg.lambda_min <= baseline <= cfg.lambda_max
    assert cfg.lambda_min <= both_high <= cfg.lambda_max
    assert higher_edge >= baseline
    assert higher_vol >= baseline
    assert both_high >= higher_edge
    assert both_high >= higher_vol


def test_ema_update_formula() -> None:
    assert _update_ema_abs_return(current=0.0, abs_return=0.08, alpha=0.2) == 0.016
    assert _update_ema_abs_return(current=0.5, abs_return=0.1, alpha=1.0) == 0.1


def test_state_hybrid_thinning_is_deterministic(tmp_path) -> None:
    base = preset_config("validation")
    cfg1 = SimConfig(
        **{
            **base.__dict__,
            "seed": 19,
            "num_sessions": 1,
            "db_path": str(tmp_path / "det_1.db"),
            "outdir": tmp_path / "out1",
        }
    )
    cfg2 = SimConfig(
        **{
            **base.__dict__,
            "seed": 19,
            "num_sessions": 1,
            "db_path": str(tmp_path / "det_2.db"),
            "outdir": tmp_path / "out2",
        }
    )

    run1 = run_abm(cfg1)
    run2 = run_abm(cfg2)

    def _trade_signature(database_url: str, sid: int) -> list[tuple]:
        db_factory = _build_session_factory(database_url)
        with db_factory() as db:
            rows = db.execute(
                select(Trade.round_id, Trade.participant_id, Trade.direction, Trade.quantity, Trade.cost)
                .join(Round, Trade.round_id == Round.id)
                .join(Market, Round.market_id == Market.id)
                .where(Market.session_id == sid, Market.is_practice.is_(False))
                .order_by(Trade.id)
            ).all()
        return [(int(r[0]), str(r[1]), str(r[2]), int(r[3]), float(r[4])) for r in rows]

    sig1 = _trade_signature(run1.database_url, run1.session_ids[0])
    sig2 = _trade_signature(run2.database_url, run2.session_ids[0])
    assert sig1 == sig2
