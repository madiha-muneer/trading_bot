from src.models.strategy_model import Order
from src.backtest import simulate_fills
from helpers import minute, buy, sell
from src import config


# ---------------- limit buy ----------------


def test_buy_does_not_fill_when_price_stays_above():
    book = {"b": buy(100.0, oid="b")}
    fills = simulate_fills(book, [minute(102, 103, 101, 102)])
    assert fills == []
    assert "b" in book  # order still resting


def test_buy_does_not_fill_on_exact_touch():
    # low == limit price: touched, not traded THROUGH -> no fill (conservative rule)
    book = {"b": buy(100.0, oid="b")}
    fills = simulate_fills(book, [minute(101, 101, 100.0, 100.5)])
    assert fills == []
    assert "b" in book


def test_buy_fills_when_traded_through():
    book = {"b": buy(100.0, qty=2.0, oid="b")}
    fills = simulate_fills(book, [minute(101, 101, 99.9, 100.2)])
    assert len(fills) == 1
    f = fills[0]
    assert f.order_id == "b"
    assert f.price == 100.0  # fills at OUR limit price, not the low
    assert f.quantity == 2.0
    assert abs(f.fee - 100.0 * 2.0 * config.FEE_RATE) < 1e-9
    assert "b" not in book  # removed from the book


# ---------------- limit sell ----------------


def test_sell_does_not_fill_when_price_stays_below():
    book = {"s": sell(110.0, oid="s")}
    fills = simulate_fills(book, [minute(105, 108, 104, 107)])
    assert fills == []
    assert "s" in book


def test_sell_does_not_fill_on_exact_touch():
    book = {"s": sell(110.0, oid="s")}
    fills = simulate_fills(book, [minute(105, 110.0, 104, 108)])
    assert fills == []
    assert "s" in book


def test_sell_fills_when_traded_through():
    book = {"s": sell(110.0, oid="s")}
    fills = simulate_fills(book, [minute(105, 110.1, 104, 109)])
    assert len(fills) == 1
    assert fills[0].price == 110.0
    assert "s" not in book


# ---------------- sequencing (why 1m data exists) ----------------


def test_first_crossing_in_time_wins():
    # buy at 100 and sell at 110 both resting.
    # minute 1 dips through 100, minute 2 rises through 110.
    # fills must come back in that time order: buy first, then sell.
    book = {"b": buy(100.0, oid="b"), "s": sell(110.0, oid="s")}
    fills = simulate_fills(
        book,
        [
            minute(101, 102, 99.5, 100.0, t=1),
            minute(100, 110.5, 100, 110.0, t=2),
        ],
    )
    assert [f.order_id for f in fills] == ["b", "s"]
    assert book == {}


def test_one_minute_cannot_fill_the_same_order_twice():
    # order fills in minute 1; minute 2 also crosses -> must NOT fill again
    book = {"b": buy(100.0, oid="b")}
    fills = simulate_fills(
        book,
        [minute(101, 101, 99.0, 99.5, t=1), minute(99, 100.5, 98.0, 99.0, t=2)],
    )
    assert len(fills) == 1


# ---------------- market sell (liquidation) ----------------


def test_market_sell_fills_at_first_open_with_slippage():
    book = {"liq": Order(id="liq", kind="market_sell", price=0.0, quantity=3.0)}
    fills = simulate_fills(
        book, [minute(100.0, 101, 99, 100, t=1), minute(100, 105, 100, 104, t=2)]
    )
    assert len(fills) == 1
    f = fills[0]
    expected_px = 100.0 * (1 - config.SLIPPAGE_MARKET)
    assert abs(f.price - expected_px) < 1e-9
    assert abs(f.fee - expected_px * 3.0 * config.FEE_RATE) < 1e-9
    assert "liq" not in book


def test_empty_minutes_change_nothing():
    # exchange maintenance gap: no minutes exist -> no fills, orders survive
    book = {"b": buy(100.0, oid="b")}
    fills = simulate_fills(book, [])
    assert fills == []
    assert "b" in book
