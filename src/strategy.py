import config
from dataclasses import replace
from models.detector_model import Band, Candle, DetectorState, StepsResult
from models.strategy_model import Order, Rung, StrategyState, Fill


def _order_id(state: StrategyState, rung: Rung, side: str) -> str:
    return f"{state.regime_start}-r{rung.index}-c{rung.cycles}-{side}"


def _build_ladder(band: Band, regime_start: int) -> list[Rung]:
    height = band.high_price - band.low_price
    step = height / config.LADDER_RUNGS
    mid = band.mid

    levels = []
    level = band.low_price
    while level <= mid + 1e-9:
        levels.append(level)
        level += step

    capital_per_rung = config.CAPITAL_PER_REGIME / len(levels)
    return [
        Rung(
            index=i,
            buy_price=lvl,
            sell_price=lvl + step,
            quantity=capital_per_rung / lvl,
        )
        for i, lvl in enumerate(levels)
    ]


def deployed_count(days_in_regime: int, total_rung: int) -> int:
    if not config.RAMP_ENABLED:
        return total_rung
    extra = days_in_regime // config.RAMP_ADD_EVERY_DAYS
    return min(total_rung, config.RAMP_INITIAL_RUNGS + extra)


# strategy
def strategy_step(
    state: StrategyState,
    detector_state: DetectorState,
    detector_result: StepsResult,
    fills: list[Fill],
    candle: Candle,
) -> tuple[StrategyState, list[Order]]:
    orders: list[Order] = []

    # fills from last step
    for f in fills:
        rung = _find_rung_by_order(state, f.order_id)
        if rung is None:
            continue
        state.fees_paid += f.fee

        if f.order_id.endswith("-buy"):
            rung.status = "holding"
            rung.buy_fee = f.fee

        elif f.order_id.endswith("-sell"):
            state.realized_profitandlosee += (
                (f.price - rung.buy_price) * f.quantity - f.fee - rung.buy_fee
            )
            rung.buy_fee = 0.0
            rung.status = "idle"
            rung.cycles += 1

        if f.order_id in state.open_order_ids:
            state.open_order_ids.remove(f.order_id)

    # regime jus turned off
    if state.active and not detector_result.regime_on:
        for order_id in state.open_order_ids:
            orders.append(Order(id=order_id, kind="cancel", price=0.0, quantity=0.0))
        held = sum(
            r.quantity for r in state.rungs if r.status in ("holding", "sell_open")
        )
        if held > 0:
            orders.append(
                Order(
                    id=f"{state.regime_start}-liquidate",
                    kind="market_sell",
                    price=0.0,
                    quantity=held,
                )
            )
        new_state = replace(
            state, active=False, rungs=[], open_order_ids=[], days_in_regime=0
        )
        return new_state, orders

    # regime_jus turned ON---build ladder
    if detector_result.changed and detector_result.regime_on:
        assert detector_state.frozen_band is not None
        state = StrategyState(
            active=True,
            regime_start=candle.open_time,
            rungs=_build_ladder(
                band=detector_state.frozen_band, regime_start=candle.open_time
            ),
            days_in_regime=0,
            realized_profitandlosee=state.realized_profitandlosee,
            fees_paid=state.fees_paid,
        )

    if not state.active:
        return state, orders

    # normal ON days
    state.days_in_regime += 1
    allowed = deployed_count(
        days_in_regime=state.days_in_regime, total_rung=len(state.rungs)
    )
    for rung in state.rungs:
        if not rung.deployed and rung.index < allowed:
            rung.deployed = True

        if not rung.deployed:
            continue

        if rung.status == "idle":
            odr_id = _order_id(state=state, rung=rung, side="buy")
            orders.append(
                Order(
                    id=odr_id,
                    kind="limit_buy",
                    price=rung.buy_price,
                    quantity=rung.quantity,
                )
            )
            state.open_order_ids.append(odr_id)
            rung.status = "buy_open"
        elif rung.status == "holding":
            odr_id = _order_id(state=state, rung=rung, side="sell")
            orders.append(
                Order(
                    id=odr_id,
                    kind="limit_sell",
                    price=rung.sell_price,
                    quantity=rung.quantity,
                )
            )
            state.open_order_ids.append(odr_id)
            rung.status = "sell_open"

    return state, orders


def _find_rung_by_order(state: StrategyState, order_id: str) -> Rung | None:
    try:
        rung_part = order_id.split("-")[1]
        idx = int(rung_part[1:])
        return state.rungs[idx]
    except (IndexError, ValueError):
        return None
