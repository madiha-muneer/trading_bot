from src import config
from src.models.detector_model import Candle
from src.models.strategy_model import Fill, Order


def simulate_fills(
    open_orders: dict[str, Order], minutes_candles: list[Candle]
) -> list[Fill]:
    fills: list[Fill] = []

    if not minutes_candles:
        return fills

    first_open = minutes_candles[0].open_price
    for order in list(open_orders.values()):
        if order.kind == "market_sell":
            px = first_open * (1 - config.SLIPPAGE_MARKET)
            fee = px * order.quantity * config.FEE_RATE
            fills.append(
                Fill(
                    order_id=order.id,
                    price=px,
                    quantity=order.quantity,
                    fee=fee,
                )
            )
            del open_orders[order.id]

    for candle in minutes_candles:
        for order in list(open_orders.values()):

            if order.kind == "limit_buy" and candle.low_price < order.price:
                fee = order.price * order.quantity * config.FEE_RATE
                fills.append(
                    Fill(
                        order_id=order.id,
                        price=order.price,
                        quantity=order.quantity,
                        fee=fee,
                    )
                )
                del open_orders[order.id]

            elif order.kind == "limit_sell" and candle.high_price > order.price:
                fee = order.price * order.quantity * config.FEE_RATE
                fills.append(
                    Fill(
                        order_id=order.id,
                        price=order.price,
                        quantity=order.quantity,
                        fee=fee,
                    )
                )
                del open_orders[order.id]
    return fills
