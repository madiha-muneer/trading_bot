from datetime import datetime, timezone
from detector import step, count_touches
from models import DetectorState, Band
import config, db


def day(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d")


def main():
    con = db.get_con()
    candles = db.load_candles(con)
    con.close()

    today_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    if candles and day(candles[-1].open_time) == today_utc:
        candles = candles[:-1]

    print(
        f"loaded {len(candles)} close daily candles /n {day(candles[0].open_time)} - {day(candles[-1].open_time)} /n"
    )
    state = DetectorState()
    periods = []
    current = None
    tally = {"slope": 0, "atr": 0, "width": 0, "touch": 0, "all": 0, "n": 0}

    for i in range(config.WINDOW, len(candles) + 1):
        window = candles[i - config.WINDOW : i]
        today = window[-1]
        state, result = step(state=state, window=window)

        # inside the loop, after: state, res = step(state, window)
        if not result.regime_on:  # only count days we're hunting
            tally["n"] += 1
            ok_slope = result.slope_atr < config.ON_SLOPE_MAX
            ok_atr = config.ON_ATR_PCT_MIN <= result.atr_pct <= config.ON_ATR_PCT_MAX
            ok_width = result.width_pct < config.ON_RANGE_WIDTH_MAX
            ok_touch = (
                result.top_touches >= config.ON_MIN_TOUCHES
                and result.bottom_touches >= config.ON_MIN_TOUCHES
            )
            for k, ok in [
                ("slope", ok_slope),
                ("atr", ok_atr),
                ("width", ok_width),
                ("touch", ok_touch),
            ]:
                tally[k] += ok
            tally["all"] += all([ok_slope, ok_atr, ok_width, ok_touch])

        if result.changed and result.regime_on:
            current = {"start": today.open_time, "band": state.frozen_band}
        elif result.changed and not result.regime_on:
            current["end"] = today.open_time
            current["exit"] = result.reason
            periods.append(current)

    # after the loop:
    n = tally["n"]
    for k in ["slope", "atr", "width", "touch", "all"]:
        print(f"{k:>6}: passes {tally[k]/n*100:5.1f}% of days")

    if current is not None:
        current["end"] = candles[-1].open_time
        current["exit"] = "(still on)"
        periods.append(current)

    # report
    print(
        f"{'#':>2}  {'start':<12}{'end':<12}{'days':>5}  "
        f"{'band low':>10}{'band high':>11}{'width%':>8}  exit"
    )
    print("-" * 78)
    total_days = 0
    for number, period in enumerate(periods, 1):
        days = int((period["end"] - period["start"]) / (24 * 3600 * 1000))
        total_days += days
        band = period["band"]
        print(
            f"{number:>2}  {day(period['start']):<12}{day(period['end']):<12}{days:>5}  "
            f"{band.low_price:>10.0f}{band.high_price:>11.0f}{band.width_pct:>8.1f}  {period['exit']}"
        )

    if periods:
        exits = {}
        for p in periods:
            exits[p["exit"]] = exits.get(p["exit"], 0) + 1
        print("-" * 78)
        print(
            f"{len(periods)} regime period(s), {total_days} days ON total "
            f"({total_days / (len(candles) - config.WINDOW) * 100:.0f}% of history)"
        )
        print("exit causes:", ", ".join(f"{k}={v}" for k, v in sorted(exits.items())))
    else:
        print("No regime periods detected. Thresholds are probably too strict.")


if __name__ == "__main__":
    main()
