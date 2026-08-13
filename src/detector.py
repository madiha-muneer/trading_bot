import config
from models import Candle, Band, StepsResult, DetectorState


def atr(window: list[Candle], period: int):
    trs = []
    for prev, curr in zip(window[-period - 1 : -1], window[-period:]):
        tr = max(
            curr.high_price - curr.low_price,
            abs(curr.high_price - prev.close_price),
            abs(curr.low_price - prev.close_price),
        )
        trs.append(tr)
    return sum(trs) / len(trs)


def linreg_slope(closes: list[float]) -> float:
    n = len(closes)
    days = range(n)
    mean_x = (n - 1) / 2
    mean_y = sum(closes) / n
    num = sum((x - mean_x) * (y - mean_y) for x, y in zip(days, closes))
    den = sum((x - mean_x) ** 2 for x in days)
    return num / den


def count_touches(closes: list[float], band: Band) -> tuple[int, int]:
    third = (band.high_price - band.low_price) / 3
    top_edge = band.high_price - third
    bottom_edge = band.low_price + third

    top = bottom = 0
    prev_zone = None
    for price in closes:
        new_zone = (
            "top" if price >= top_edge else "bottom" if price <= bottom_edge else "mid"
        )
        if new_zone == "top" and prev_zone != "top":
            top += 1
        if new_zone == "bottom" and prev_zone != "bottom":
            bottom += 1
        prev_zone = new_zone
    return top, bottom


def step(
    state: DetectorState, window: list[Candle]
) -> tuple[DetectorState, StepsResult]:
    assert len(window) == config.WINDOW

    today = window[-1]
    closes = [price.close_price for price in window]

    a = atr(window, config.ATR_PERIOD)
    atr_pct = (a / today.close_price) * 100
    slope_atr = abs(linreg_slope(closes)) / a
    rolling_band = Band(
        high_price=max(price.close_price for price in window),
        low_price=min(
            price.close_price for price in window
        ),  # changes from price.low_price to price.close_price
    )
    width_pct = rolling_band.width_pct
    top_touches, bott_touches = count_touches(closes, rolling_band)

    def result(
        changes: bool,
        reason: str,
        on: bool,
        breach_atr: float = 0.0,
        direction: str = "",
    ) -> StepsResult:
        return StepsResult(
            regime_on=on,
            changed=changes,
            reason=reason,
            atr_pct=atr_pct,
            slope_atr=slope_atr,
            top_touches=top_touches,
            bottom_touches=bott_touches,
            width_pct=width_pct,
            exit_breach_atr=breach_atr,
            exit_direction=direction,
        )

    if not state.regime_on:
        if state.last_off_time is not None:
            days_since_off = (
                today.open_time - state.last_off_time
            ) / config.INTERVAL_MS
            if days_since_off < config.COOLDOWN_DAYS:
                return state, result(changes=False, reason="cooldown", on=False)
        # turn on conditions
        conditions = (
            slope_atr < config.ON_SLOPE_MAX
            and config.ON_ATR_PCT_MIN <= atr_pct <= config.ON_ATR_PCT_MAX
            and config.ON_RANGE_WIDTH_MIN < width_pct < config.ON_RANGE_WIDTH_MAX
            and rolling_band.low_price <= today.close_price <= rolling_band.high_price
            and top_touches >= config.ON_MIN_TOUCHES
            and bott_touches >= config.ON_MIN_TOUCHES
        )

        if not conditions:
            return state, result(changes=False, reason="", on=False)

        new_state = DetectorState(
            regime_on=True,
            frozen_band=rolling_band,
            breach_count=0,
            last_off_time=state.last_off_time,
        )
        return new_state, result(changes=True, reason="turn_on", on=True)

    # frozen band breakout
    band = state.frozen_band
    assert band is not None

    def turn_off(
        reason: str, breach_atr: float = 0.0, direction: str = ""
    ) -> tuple[DetectorState, StepsResult]:
        new_state = DetectorState(
            regime_on=False,
            frozen_band=None,
            breach_count=0,
            last_off_time=today.open_time,
        )
        return new_state, result(
            changes=True,
            reason=reason,
            on=False,
            breach_atr=breach_atr,
            direction=direction,
        )

    breach = 0.0
    direction = ""
    if today.close_price > band.high_price:
        breach = today.close_price - band.high_price
        direction = "up"
    elif today.close_price < band.low_price:
        breach = band.low_price - today.close_price
        direction = "down"
    breach_atr = breach / a if a > 0 else 0.0
    if breach >= config.HARD_KILL_ATR * a:
        return turn_off("Hard Break!", breach_atr=breach_atr, direction=direction)

    if breach >= config.SOFT_KILL_ATR * a:
        new_breach_count = state.breach_count + 1
        if new_breach_count >= config.SOFT_KILL_DAYS:
            return turn_off("Soft Break!", breach_atr=breach_atr, direction=direction)

        new_state = DetectorState(
            regime_on=True,
            frozen_band=band,
            breach_count=new_breach_count,
            last_off_time=state.last_off_time,
        )
        return new_state, result(
            changes=False,
            reason="soft_breach_pending",
            on=True,
            breach_atr=breach_atr,
            direction=direction,
        )
    else:
        state = DetectorState(
            regime_on=True,
            frozen_band=band,
            breach_count=0,
            last_off_time=state.last_off_time,
        )

    if slope_atr > config.OFF_SLOPE_MIN:
        return turn_off("slope", breach_atr=breach_atr, direction=direction)
    if atr_pct > config.OFF_ATR_PCT_MAX:
        return turn_off("vol(atr_pct) high", breach_atr=breach_atr, direction=direction)
    if atr_pct < config.OFF_ATR_PCT_MIN:
        return turn_off("vol(atr_pct) low", breach_atr=breach_atr, direction=direction)
    if width_pct > config.OFF_RANGE_WIDTH_MAX:
        return turn_off("width", breach_atr=breach_atr, direction=direction)

    return state, result(
        changes=False, reason="", on=True, breach_atr=breach_atr, direction=direction
    )
