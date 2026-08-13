from dataclasses import dataclass


@dataclass(frozen=True)
class Candle:
    open_time: int
    open_price: float
    high_price: float
    low_price: float
    close_price: float
    volume: float


@dataclass(frozen=True)
class Band:
    high_price: float
    low_price: float

    @property
    def mid(self) -> float:
        return (self.high_price + self.low_price) / 2

    @property
    def width_pct(self) -> float:
        return (self.high_price - self.low_price) / self.mid * 100


@dataclass(frozen=True)
class DetectorState:
    regime_on: bool = False
    frozen_band: Band | None = None
    breach_count: int = 0
    last_off_time: int | None = None


@dataclass(frozen=True)
class StepsResult:
    regime_on: bool
    changed: bool
    reason: str
    slope_atr: float
    atr_pct: float
    top_touches: int
    bottom_touches: int
    width_pct: float
