"""
structure.py — HTF bias detection using proper swing-point series.

Logic:
  1. Identify all swing highs and lows (N candles on each side).
  2. Look at the last 4 swings of each type.
  3. Count consecutive HH/HL or LL/LH to determine bias and strength.
  4. Cache range as (last swing low -> last swing high).
  5. BOS = price closes beyond the cached range -> invalidates cache.
"""

from config import SWING_LOOKBACK


def get_all_swings(df, lookback=SWING_LOOKBACK):
    """
    Returns two lists of dicts: swing_highs and swing_lows.
    Each entry: {'idx': int, 'price': float}
    A point qualifies when it is the extreme vs `lookback` candles on each side.
    """
    swing_highs, swing_lows = [], []

    for i in range(lookback, len(df) - lookback):
        h = float(df["high"].iloc[i])
        l = float(df["low"].iloc[i])

        is_sh = (
            all(h >= float(df["high"].iloc[i - j]) for j in range(1, lookback + 1)) and
            all(h >= float(df["high"].iloc[i + j]) for j in range(1, lookback + 1))
        )
        is_sl = (
            all(l <= float(df["low"].iloc[i - j]) for j in range(1, lookback + 1)) and
            all(l <= float(df["low"].iloc[i + j]) for j in range(1, lookback + 1))
        )

        if is_sh:
            swing_highs.append({"idx": i, "price": h})
        if is_sl:
            swing_lows.append({"idx": i, "price": l})

    return swing_highs, swing_lows


def determine_bias(df):
    """
    Returns (bias, series_count, range_low, range_high).

    bias         : "BULLISH" | "BEARISH" | "RANGE"
    series_count : number of confirmed HH/HL or LL/LH pairs
    range_low    : price of the last confirmed swing low
    range_high   : price of the last confirmed swing high
    """
    sh, sl = get_all_swings(df)

    if len(sh) < 2 or len(sl) < 2:
        return "RANGE", 0, float(df["low"].min()), float(df["high"].max())

    recent_highs = sh[-4:]
    recent_lows  = sl[-4:]

    hh = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i]["price"] > recent_highs[i - 1]["price"])
    hl = sum(1 for i in range(1, len(recent_lows))  if recent_lows[i]["price"]  > recent_lows[i - 1]["price"])
    ll = sum(1 for i in range(1, len(recent_lows))  if recent_lows[i]["price"]  < recent_lows[i - 1]["price"])
    lh = sum(1 for i in range(1, len(recent_highs)) if recent_highs[i]["price"] < recent_highs[i - 1]["price"])

    range_high = recent_highs[-1]["price"]
    range_low  = recent_lows[-1]["price"]

    if hh >= 1 and hl >= 1:
        return "BULLISH", min(hh, hl) + 1, range_low, range_high

    if ll >= 1 and lh >= 1:
        return "BEARISH", min(ll, lh) + 1, range_low, range_high

    return "RANGE", 0, range_low, range_high


def check_bos(df, state):
    """
    Returns True if a new BOS has occurred or it is the first run.
    A BOS means price has closed beyond the cached HTF range, invalidating it.
    """
    if state.htf_range_high is None or state.htf_range_low is None:
        return True

    last_close = float(df["close"].iloc[-1])

    if state.htf_bias == "BULLISH" and last_close < state.htf_range_low:
        print("BOS DOWN — recalculating HTF bias")
        return True

    if state.htf_bias == "BEARISH" and last_close > state.htf_range_high:
        print("BOS UP — recalculating HTF bias")
        return True

    return False
