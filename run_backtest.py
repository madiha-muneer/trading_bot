from datetime import datetime, timezone

from src import config, db
from src.backtest import simulate_fills
from src.detector import step
from src.models.detector_model import DetectorState
from src.models.strategy_model import StrategyState, Order
from src.strategy import strategy_step

# debugging period 12
DEBUG_FROM = "2023-09-18"
DEBUG_TO = "2023-10-22"


def day_str(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d")


def load_minutes(con, day_start_ms: int) -> list:
    """All 1m candles inside one daily candle's time span."""
    rows = con.execute(
        """
        SELECT open_time, open_price, high_price, low_price, close_price, volume
        FROM candles
        WHERE symbol = ? AND timeframe = '1m'
          AND open_time >= ? AND open_time < ?
        ORDER BY open_time ASC
        """,
        (config.SYMBOL, day_start_ms, day_start_ms + config.INTERVAL_MS),
    ).fetchall()
    from src.models.detector_model import Candle

    return [Candle(*r) for r in rows]


def apply_orders(book: dict[str, Order], new_orders: list[Order]) -> None:
    for o in new_orders:
        if o.kind == "cancel":
            book.pop(o.id, None)
        else:
            book[o.id] = o


def main() -> None:
    con = db.get_con()
    daily = db.load_candles(con)  # 1d candles, oldest first

    # drop today's still-open candle
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if daily and day_str(daily[-1].open_time) == today_utc:
        daily = daily[:-1]

    det_state = DetectorState()
    strat_state = StrategyState()
    book: dict[str, Order] = {}

    # ledger (the backtester's own truth)
    cash = config.CAPITAL_PER_REGIME
    coins = 0.0
    start_equity = cash

    equity_curve: list[float] = []
    periods: list[dict] = []
    current: dict | None = None

    for i in range(config.WINDOW, len(daily) + 1):
        window = daily[i - config.WINDOW : i]
        today = window[-1]

        # ---- 1) today's price action fills yesterday's resting orders ----
        minutes = load_minutes(con, today.open_time)
        fills = simulate_fills(book, minutes)

        # ledger update from fills
        for f in fills:
            if f.order_id.endswith("-buy"):
                cash -= f.price * f.quantity + f.fee
                coins += f.quantity
            else:  # -sell or -liquidate
                cash += f.price * f.quantity - f.fee
                coins -= f.quantity
            if current is not None:
                current["fills"] += 1
                if f.order_id.endswith("-sell"):
                    current["cycles"] += 1

        # ---- 2) evening: run the brains on today's closed candle ----
        det_state, det_result = step(det_state, window)
        strat_state, new_orders = strategy_step(
            strat_state, det_state, det_result, fills, today
        )

        # ---- 3) tonight's new orders rest starting tomorrow ----
        apply_orders(book, new_orders)
        if DEBUG_FROM <= day_str(today.open_time) <= DEBUG_TO:
            print(
                f"\n== {day_str(today.open_time)}  "
                f"low {today.low_price:,.0f}  high {today.high_price:,.0f}  "
                f"close {today.close_price:,.0f}  "
                f"regime={'ON' if det_result.regime_on else 'off'}"
            )
            for f in fills:
                print(
                    f"   FILL    {f.order_id}  @ {f.price:,.0f}  qty {f.quantity:.5f}"
                )
            for o in book.values():
                print(f"   resting {o.kind:<11} @ {o.price:,.0f}   ({o.id})")
            if strat_state.active:
                for r in strat_state.rungs:
                    print(
                        f"   rung{r.index}  buy@{r.buy_price:,.0f} -> "
                        f"sell@{r.sell_price:,.0f}  status={r.status}  "
                        f"deployed={r.deployed}  cycles={r.cycles}"
                    )

        # ---- 4) diary ----
        equity = cash + coins * today.close_price
        equity_curve.append(equity)

        if det_result.changed and det_result.regime_on:
            current = {
                "start": today.open_time,
                "start_equity": equity,
                "band": det_state.frozen_band,
                "fills": 0,
                "cycles": 0,
            }
        elif det_result.changed and not det_result.regime_on and current is not None:
            # note: the liquidation market_sell fills TOMORROW, so the
            # final period equity is captured one day late on purpose
            current["end"] = today.open_time
            current["exit"] = det_result.reason
            current["pending_close"] = True
            periods.append(current)
            current = None
        elif periods and periods[-1].get("pending_close"):
            # first day after a kill: liquidation has now filled
            periods[-1]["net"] = equity - periods[-1]["start_equity"]
            periods[-1].pop("pending_close")

    # a still-open period at data end
    if current is not None:
        current["end"] = daily[-1].open_time
        current["exit"] = "(still on)"
        current["net"] = (cash + coins * daily[-1].close_price) - current[
            "start_equity"
        ]
        periods.append(current)
    if periods and periods[-1].get("pending_close"):
        periods[-1]["net"] = equity_curve[-1] - periods[-1]["start_equity"]
        periods[-1].pop("pending_close")

    con.close()

    # ---------------- report ----------------
    print(
        f"{'#':>2}  {'start':<12}{'end':<12}{'days':>5}{'cycles':>7}"
        f"{'net $':>9}{'net %':>8}  exit"
    )
    print("-" * 70)
    total_on_days = 0
    for n, p in enumerate(periods, 1):
        days = int((p["end"] - p["start"]) / config.INTERVAL_MS)
        total_on_days += days
        net = p.get("net", 0.0)
        net_pct = net / config.CAPITAL_PER_REGIME * 100
        print(
            f"{n:>2}  {day_str(p['start']):<12}{day_str(p['end']):<12}"
            f"{days:>5}{p['cycles']:>7}{net:>9.2f}{net_pct:>8.2f}  {p['exit']}"
        )

    final_equity = equity_curve[-1]
    total_net = final_equity - start_equity
    total_pct = total_net / start_equity * 100

    # max drawdown on the equity curve
    peak, max_dd = equity_curve[0], 0.0
    for e in equity_curve:
        peak = max(peak, e)
        max_dd = max(max_dd, (peak - e) / peak)

    # the hurdle: income per ON-day
    per_on_day_pct = (
        total_net / config.CAPITAL_PER_REGIME * 100 / total_on_days
        if total_on_days
        else 0.0
    )

    first, last = daily[config.WINDOW - 1], daily[-1]
    buy_hold_pct = (last.close_price / first.close_price - 1) * 100

    print("-" * 70)
    print(f"periods: {len(periods)}   ON days: {total_on_days}")
    print(f"net result: {total_net:+.2f} USDT ({total_pct:+.2f}% of capital)")
    print(f"per ON-day: {per_on_day_pct:+.3f}%   (hurdle: +0.13%/day)")
    print(f"max drawdown: {max_dd * 100:.1f}%")
    print(f"buy & hold same span: {buy_hold_pct:+.1f}%")
    print(
        f"strategy's own pnl book says: {strat_state.realized_profitandlosee:+.2f} "
        f"(cross-check; will differ by liquidation losses)"
    )


if __name__ == "__main__":
    main()
