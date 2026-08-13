import sqlite3
from config import SYMBOL, INTERVAL, INTERVAL_MS, DB_FILE
from datetime import datetime, timezone
import config
from models import Candle


def get_con() -> sqlite3.Connection:
    return sqlite3.connect(config.DB_FILE)


def get_db() -> sqlite3.Connection:
    con = sqlite3.connect(DB_FILE)
    con.execute("PRAGMA JOURNAL_MODE = WAL;")
    con.execute(
        """
    CREATE TABLE IF NOT EXISTS candles (
        symbol TEXT NOT NULL,
        timeframe TEXT NOT NULL,
        open_time INTEGER NOT NULL,
        open_price REAL NOT NULL,
        high_price REAL NOT NULL,
        low_price REAL NOT NULL,
        close_price REAL NOT NULL,
        volume REAL NOT NULL,
        PRIMARY KEY (symbol, timeframe, open_time)
    )
    """
    )
    return con


def last_stored_open_time(
    con: sqlite3.Connection, symbol: str, timeframe: str
) -> int | None:
    row = con.execute(
        "SELECT MAX(open_time) FROM candles WHERE symbol = ? AND timeframe = ?",
        (symbol, timeframe),
    ).fetchone()
    return row[0]


def store_batch_klines(con: sqlite3.Connection, batch: list[list]):
    rows = [
        (
            SYMBOL,
            INTERVAL,
            k[0],
            float(k[1]),
            float(k[2]),
            float(k[3]),
            float(k[4]),
            float(k[5]),
        )
        for k in batch
    ]
    con.executemany(
        "INSERT OR REPLACE INTO candles (symbol, timeframe, open_time, open_price, high_price, low_price, close_price, volume) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
        rows,
    )
    con.commit()


def check_gaps(con: sqlite3.Connection) -> None:
    gaps = con.execute(
        """
        SELECT prev_time, open_time
        FROM (
            SELECT open_time,
                   LAG(open_time) OVER (ORDER BY open_time) AS prev_time
            FROM candles
            WHERE symbol = ? AND timeframe = ?
        )
        WHERE prev_time IS NOT NULL
          AND open_time - prev_time <> ?
        """,
        (SYMBOL, INTERVAL, INTERVAL_MS),
    ).fetchall()

    if not gaps:
        print("Gap check: OK, no missing candles.")
    else:
        print(f"Gap check: FOUND {len(gaps)} gap(s):")
        for prev_time, open_time in gaps:
            a = datetime.fromtimestamp(prev_time / 1000, timezone.utc).isoformat()
            b = datetime.fromtimestamp(open_time / 1000, timezone.utc).isoformat()
            print(f"  missing between {a} and {b}")

    (count,) = con.execute(
        "SELECT COUNT(*) FROM candles WHERE symbol = ? AND timeframe = ?",
        (SYMBOL, INTERVAL),
    ).fetchone()
    print(f"Total candles in DB: {count}")


def load_candles(con: sqlite3.Connection) -> list[Candle]:
    rows = con.execute(
        "SELECT open_time, open_price, high_price, low_price, close_price, volume FROM candles WHERE symbol = ? AND timeframe = ?",
        (SYMBOL, INTERVAL),
    ).fetchall()
    return [Candle(*c) for c in rows]
