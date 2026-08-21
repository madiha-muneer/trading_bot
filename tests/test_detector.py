from src.detector import atr, count_touches, linreg_slope
from src.models.detector_model import Band
from tests.helpers import minute


def test_count_touches_on_zigzag():
    # closes bounce 100 -> 110 -> 100 -> 110 -> 100: both thirds visited repeatedly
    closes = ([100 + i for i in range(11)] + [110 - i for i in range(11)]) * 2
    band = Band(low_price=min(closes), high_price=max(closes))
    top, bottom = count_touches(closes[:40], band)
    assert top >= 2
    assert bottom >= 2


def test_count_touches_sitting_at_edge_counts_once():
    # drift up into the top third and STAY there: one entry, one touch
    closes = [100, 101, 102, 108, 109, 109, 109, 109]
    band = Band(low_price=100.0, high_price=110.0)
    top, bottom = count_touches(closes, band)
    assert top == 1


def test_flat_series_has_zero_slope():
    closes = [100.0] * 30
    assert abs(linreg_slope(closes)) < 1e-9


def test_atr_on_constant_candles():
    # every candle: high 102, low 98, close 100 -> TR is always 4
    candles = [minute(100, 102, 98, 100, t=i) for i in range(20)]
    assert abs(atr(candles, period=14) - 4.0) < 1e-9
