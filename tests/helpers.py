from src.models.detector_model import Candle
from src.models.strategy_model import Order


def minute(o: float, h: float, l: float, c: float, t: int = 0) -> Candle:
    """Build a 1m candle. Keyword args keep field order mistakes impossible."""
    return Candle(
        open_time=t,
        open_price=o,
        high_price=h,
        low_price=l,
        close_price=c,
        volume=1.0,
    )


def buy(price: float, qty: float = 1.0, oid: str = "1-r0-c0-buy") -> Order:
    return Order(id=oid, kind="limit_buy", price=price, quantity=qty)


def sell(price: float, qty: float = 1.0, oid: str = "1-r0-c0-sell") -> Order:
    return Order(id=oid, kind="limit_sell", price=price, quantity=qty)
