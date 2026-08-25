from datetime import datetime, timezone
import time
import requests
import sqlite3

from src.config import SYMBOL, INTERVAL, START_DATE, BASE_URL, LIMIT, INTERVAL_MS
from src.db import get_db, last_stored_open_time, store_batch_klines, check_gaps


def fetch_batch_klines(start_time: int) -> list[list]:
    resp = requests.get(
        BASE_URL,
        params={
            "symbol": SYMBOL,
            "interval": INTERVAL,
            "startTime": start_time,
            "limit": LIMIT,
        },
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def sync(con: sqlite3.Connection) -> None:
    last = last_stored_open_time(con, symbol=SYMBOL, timeframe=INTERVAL)
    cursor = (last + 1) if last is not None else START_DATE

    label = "Resuming from" if last is not None else "Fresh download from"
    print(f"{label} {datetime.fromtimestamp(cursor / 1000, timezone.utc).isoformat()}")

    total = 0
    while True:
        batch = fetch_batch_klines(cursor)
        if not batch:
            break

        store_batch_klines(con, batch)
        total += len(batch)

        last_open = batch[-1][0]
        print(
            f"Stored {len(batch)} candles up to "
            f"{datetime.fromtimestamp(last_open / 1000, timezone.utc).isoformat()}"
        )

        cursor = last_open + 1

        if len(batch) < LIMIT:
            break
        time.sleep(0.3)

    print(f"Done. {total} candles fetched/updated this run.")


if __name__ == "__main__":
    con = get_db()
    try:
        sync(con)
        check_gaps(con)
    except requests.RequestException as e:
        print(f"Sync failed: {e}")
        raise SystemExit(1)
    finally:
        con.close()
