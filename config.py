import os

# ── SYMBOLS ────────────────────────────────────────────────
SYMBOLS = ["XAU/USD", "GBP/USD", "GBP/JPY", "AUD/USD"]

# ── TIMEFRAMES ────────────────────────────────────────────
HTF = "1h"    # Higher Timeframe — structure & bias
LTF = "5min"    # Lower Timeframe — entry detection

# ── LOOP ──────────────────────────────────────────────────
LOOP_DELAY = 180   # seconds between full scan cycles

# ── API KEYS ──────────────────────────────────────────────
TWELVEDATA_API_KEY = os.environ.get("TWELVEDATA_API_KEY", "")

# ── TELEGRAM ──────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "8529456380:AAF2Ed2EoEtGRTfAX4a67Vd89KSnMUImdQc")
TELEGRAM_TOKEN     = TELEGRAM_BOT_TOKEN       # alias
TELEGRAM_CHAT_ID   = os.environ.get("TELEGRAM_CHAT_ID", "6599172354")

# ── STRATEGY SETTINGS ─────────────────────────────────────
SWING_LOOKBACK        = 2      # candles each side to confirm a swing point
MIN_RR                = 1.0    # minimum risk:reward to fire alert
INDUCEMENT_SEARCH     = 60     # how many LTF candles back to search for setup
DISPLACEMENT_FACTOR   = 1.2    # body must be X× avg body to count as displacement
HTF_CACHE             = {}     # shared cache (not used for API, only legacy compat)
