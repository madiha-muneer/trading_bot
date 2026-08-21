"""
sweep.py
Runs the backtest for every strategy variant, on a TRAIN date range
and a VALIDATE date range separately, and prints a comparison table.

Discipline this file enforces:
- every variant is judged on the SAME two windows
- a variant only "passes" if it clears the hurdle on BOTH windows
  (profitable-on-train-only = overfit, rejected)
- nothing here touches the final 2026 test months; those stay burned
  until ONE winner is chosen

Run (venv active, from project root):
    python sweep.py
"""

import itertools
import time
from datetime import datetime, timezone

from src import config, db
from src.backtest import simulate_fills
from src.detector import step
from src.models.detector_model import DetectorState
from src.models.strategy_model import Order, StrategyState
from src.strategy import strategy_step

# ---------------- what we sweep ----------------

PLACEMENTS = ["band_bottom", "price_anchor", "full_band"]
RUNGS = [4, 6, 8]
RAMP = [True, False]

# chronological splits: train, validate. 2026 stays untouched (final test).
SPLITS = {
    "train": ("2019-01-01", "2023-12-31"),
    "validate": ("2024-01-01", "2025-12-31"),
}

HURDLE_PER_DAY = 0.13  # % of capital per ON-day, our measured break-even


# ---------------- one backtest run ----------------


def day_str(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d")


def load_minutes(con, day_start_ms: int):
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


def run(con, daily, date_from: str, date_to: str) -> dict:
    """One full backtest on a date slice. Returns summary numbers only."""
    sliced = [c for c in daily if date_from <= day_str(c.open_time) <= date_to]
    if len(sliced) <= config.WINDOW:
        return {}

    det_state = DetectorState()
    strat_state = StrategyState()
    book: dict[str, Order] = {}

    cash = config.CAPITAL_PER_REGIME
    coins = 0.0
    start_equity = cash

    equity_curve = []
    on_days = 0
    cycles = 0
    n_periods = 0
    worst_period = 0.0
    period_start_equity = None

    for i in range(config.WINDOW, len(sliced) + 1):
        window = sliced[i - config.WINDOW : i]
        today = window[-1]

        # speed: only hit the 1m table when something can actually fill
        if book:
            fills = simulate_fills(book, load_minutes(con, today.open_time))
        else:
            fills = []

        for f in fills:
            if f.order_id.endswith("-buy"):
                cash -= f.price * f.quantity + f.fee
                coins += f.quantity
            else:
                cash += f.price * f.quantity - f.fee
                coins -= f.quantity
            if f.order_id.endswith("-sell"):
                cycles += 1

        det_state, det_result = step(det_state, window)
        strat_state, new_orders = strategy_step(
            strat_state, det_state, det_result, fills, today
        )
        for o in new_orders:
            if o.kind == "cancel":
                book.pop(o.id, None)
            else:
                book[o.id] = o

        equity = cash + coins * today.close_price
        equity_curve.append(equity)
        if det_result.regime_on:
            on_days += 1

        if det_result.changed and det_result.regime_on:
            n_periods += 1
            period_start_equity = equity
        elif det_result.changed and not det_result.regime_on and period_start_equity:
            worst_period = min(worst_period, equity - period_start_equity)
            period_start_equity = None

    final = equity_curve[-1]
    net = final - start_equity

    peak, max_dd = equity_curve[0], 0.0
    for e in equity_curve:
        peak = max(peak, e)
        max_dd = max(max_dd, (peak - e) / peak)

    return {
        "net_pct": net / start_equity * 100,
        "per_day": (net / start_equity * 100 / on_days) if on_days else 0.0,
        "max_dd": max_dd * 100,
        "on_days": on_days,
        "cycles": cycles,
        "periods": n_periods,
        "worst_period_pct": worst_period / config.CAPITAL_PER_REGIME * 100,
    }


# ---------------- the sweep ----------------


def main() -> None:
    con = db.get_con()
    daily = db.load_candles(con)
    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if daily and day_str(daily[-1].open_time) == today_utc:
        daily = daily[:-1]

    variants = list(itertools.product(PLACEMENTS, RUNGS, RAMP))
    print(f"{len(variants)} variants x {len(SPLITS)} splits\n")

    rows = []
    t0 = time.time()
    for n, (placement, rungs, ramp) in enumerate(variants, 1):
        # apply the variant (single-threaded, restored implicitly next loop)
        config.PLACEMENT = placement
        config.LADDER_RUNGS = rungs
        config.RAMP_ENABLED = ramp

        res = {}
        for split_name, (d_from, d_to) in SPLITS.items():
            res[split_name] = run(con, daily, d_from, d_to)

        rows.append(
            {
                "placement": placement,
                "rungs": rungs,
                "ramp": ramp,
                **{f"{s}_{k}": v for s, r in res.items() for k, v in r.items()},
            }
        )
        print(
            f"[{n}/{len(variants)}] {placement:<13} rungs={rungs} ramp={ramp}  "
            f"train {res['train'].get('per_day', 0):+.3f}%/d  "
            f"val {res['validate'].get('per_day', 0):+.3f}%/d  "
            f"({time.time() - t0:.0f}s)"
        )

    con.close()

    # ---------------- report ----------------
    def passes(r) -> bool:
        return (
            r.get("train_per_day", -9) >= HURDLE_PER_DAY
            and r.get("validate_per_day", -9) >= HURDLE_PER_DAY
        )

    rows.sort(
        key=lambda r: min(r.get("train_per_day", -9), r.get("validate_per_day", -9)),
        reverse=True,
    )

    print(
        f"\n{'placement':<13}{'rungs':>6}{'ramp':>6}"
        f"{'train%/d':>10}{'val%/d':>9}{'trainDD':>9}{'valDD':>8}"
        f"{'cycles':>8}{'worst':>8}  pass"
    )
    print("-" * 88)
    for r in rows:
        print(
            f"{r['placement']:<13}{r['rungs']:>6}{str(r['ramp']):>6}"
            f"{r.get('train_per_day', 0):>10.3f}{r.get('validate_per_day', 0):>9.3f}"
            f"{r.get('train_max_dd', 0):>9.1f}{r.get('validate_max_dd', 0):>8.1f}"
            f"{r.get('train_cycles', 0) + r.get('validate_cycles', 0):>8}"
            f"{min(r.get('train_worst_period_pct', 0), r.get('validate_worst_period_pct', 0)):>8.1f}"
            f"  {'YES' if passes(r) else '-'}"
        )

    winners = [r for r in rows if passes(r)]
    print(
        f"\n{len(winners)} variant(s) clear the {HURDLE_PER_DAY}%/day hurdle "
        f"on BOTH windows."
    )
    if not winners:
        best = rows[0]
        print(
            "Best non-passing variant for reference: "
            f"{best['placement']} rungs={best['rungs']} ramp={best['ramp']}"
        )


if __name__ == "__main__":
    main()
