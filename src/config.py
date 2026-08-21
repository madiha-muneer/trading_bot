from datetime import datetime, timezone

SYMBOL = "BTCUSDT"
# INTERVAL = "1m"
INTERVAL = "1d"

START_DATE = int(datetime(2019, 1, 1, tzinfo=timezone.utc).timestamp() * 1000)
DB_FILE = "market.db"
BASE_URL = "https://api.binance.com/api/v3/klines"

LIMIT = 1000
# INTERVAL_MS = 60 * 1000
INTERVAL_MS = 24 * 60 * 60 * 1000

# detector window
WINDOW = 30
ATR_PERIOD = 14

# turn on threshold
ON_SLOPE_MAX = 0.4
ON_ATR_PCT_MIN = 1.0
ON_ATR_PCT_MAX = 3.5
ON_MIN_TOUCHES = 2
ON_RANGE_WIDTH_MIN = 6.0
ON_RANGE_WIDTH_MAX = 12.0

# turn off threshold
OFF_SLOPE_MIN = 0.7
OFF_ATR_PCT_MIN = 0.8
OFF_ATR_PCT_MAX = 4.0
OFF_RANGE_WIDTH_MAX = 15.0

# cooldown days
COOLDOWN_DAYS = 10

# kill rule
SOFT_KILL_ATR = 1.0
SOFT_KILL_DAYS = 2
HARD_KILL_ATR = 2.0


# strategy requirements(BUY SIDE LADDER)
LADDER_RUNGS = 5
CAPITAL_PER_REGIME = 1000.0
RAMP_ENABLED = True
RAMP_INITIAL_RUNGS = 2
RAMP_ADD_EVERY_DAYS = 3

# backtesting
FEE_RATE = 0.001
SLIPPAGE_MARKET = 0.0005
