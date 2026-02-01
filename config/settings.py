# =============================================================================
# TRADING DESK CONFIGURATION
# =============================================================================
# This file contains all the settings for our trading system.
# We keep settings separate so we can change them easily without editing
# the agent code.
# =============================================================================

# -----------------------------------------------------------------------------
# INSTRUMENT SETTINGS
# -----------------------------------------------------------------------------
# The instrument we are monitoring
INSTRUMENT = "XAU/USD"

# Typical pip size for gold (0.01 = 1 cent movement)
PIP_SIZE = 0.01

# -----------------------------------------------------------------------------
# ACCOUNT SETTINGS
# -----------------------------------------------------------------------------
# Starting account balance in USD (fake money for testing)
ACCOUNT_EQUITY = 10000.00

# Maximum risk per trade as a percentage (1% = 0.01)
RISK_PER_TRADE = 0.01

# Maximum daily loss as a percentage (3% = 0.03)
MAX_DAILY_LOSS = 0.03

# Maximum number of positions open at once
MAX_CONCURRENT_POSITIONS = 2

# -----------------------------------------------------------------------------
# VOLATILITY THRESHOLDS
# -----------------------------------------------------------------------------
# These numbers define what we consider LOW, NORMAL, ELEVATED, EXTREME volatility
# Based on ATR (Average True Range) multiplier vs baseline
VOLATILITY_LOW_THRESHOLD = 0.7      # Below 70% of baseline = LOW
VOLATILITY_NORMAL_THRESHOLD = 1.3   # 70% to 130% of baseline = NORMAL
VOLATILITY_ELEVATED_THRESHOLD = 2.0 # 130% to 200% of baseline = ELEVATED
# Above 200% = EXTREME

# -----------------------------------------------------------------------------
# SPREAD THRESHOLDS (in pips)
# -----------------------------------------------------------------------------
SPREAD_ACCEPTABLE_THRESHOLD = 3.0   # Up to 3 pips = ACCEPTABLE
SPREAD_WIDE_THRESHOLD = 5.0         # Above 5 pips = WIDE

# -----------------------------------------------------------------------------
# SESSION TIMES (in UTC hours, 24-hour format)
# -----------------------------------------------------------------------------
# These define when each trading session is active
ASIA_SESSION_START = 0      # 00:00 UTC
ASIA_SESSION_END = 9        # 09:00 UTC
LONDON_SESSION_START = 7    # 07:00 UTC
LONDON_SESSION_END = 16     # 16:00 UTC
NEW_YORK_SESSION_START = 13 # 13:00 UTC
NEW_YORK_SESSION_END = 22   # 22:00 UTC

# -----------------------------------------------------------------------------
# FILE PATHS
# -----------------------------------------------------------------------------
# Where agent reports will be saved
OUTPUT_FOLDER = "outputs"
LOG_FOLDER = "logs"

# -----------------------------------------------------------------------------
# REGIME SETTINGS
# -----------------------------------------------------------------------------
# ADX threshold to determine trending vs ranging
ADX_TREND_THRESHOLD = 25    # Above 25 = trending, below = ranging

# Number of candles to look back for regime calculation
REGIME_LOOKBACK_PERIODS = 20

# -----------------------------------------------------------------------------
# STRUCTURE SETTINGS
# -----------------------------------------------------------------------------
# How many swing points to look back for structure levels
STRUCTURE_LOOKBACK_PERIODS = 50

# Minimum distance between levels (in pips) to avoid clustering
STRUCTURE_MIN_DISTANCE_PIPS = 10

# -----------------------------------------------------------------------------
# MOMENTUM SETTINGS
# -----------------------------------------------------------------------------
# Periods for momentum calculation
MOMENTUM_FAST_PERIOD = 5
MOMENTUM_SLOW_PERIOD = 20

# Threshold for acceleration detection
MOMENTUM_ACCELERATION_THRESHOLD = 0.5

# -----------------------------------------------------------------------------
# RECENCY CHECK SETTINGS
# -----------------------------------------------------------------------------
# Number of ticks to analyze for recency check
RECENCY_TICK_COUNT = 50

# Maximum age of data in seconds before considered stale
STALE_DATA_THRESHOLD_SECONDS = 5
