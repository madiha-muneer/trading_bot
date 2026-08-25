from dataclasses import dataclass, field


@dataclass(frozen=True)
class Order:
    id: str
    kind: str
    price: float
    quantity: float


@dataclass(frozen=True)
class Fill:
    order_id: str
    price: float
    quantity: float
    fee: float


@dataclass
class Rung:
    index: int
    buy_price: float
    sell_price: float
    quantity: float
    deployed: bool = False
    status: str = "idle"
    cycles: int = 0
    buy_fee: float = 0.0
    current_order_id: str = ""


@dataclass
class StrategyState:
    active: bool = False
    regime_start: int = 0
    rungs: list[Rung] = field(default_factory=list)
    days_in_regime: int = 0
    realized_profitandlosee: float = 0.0
    fees_paid: float = 0.0
    open_order_ids: list[str] = field(default_factory=list)
    days_since_buy_fill: int = 0
    anchor_gen: int = 0
