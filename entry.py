"""
entry.py — LTF inducement + liquidity sweep entry detection.

Full bullish sequence the bot looks for on the 1-min chart:

  1. Initial bullish displacement (strong impulsive candles).
  2. First pullback  — price forms a short reaction level, attracting early buyers.
  3. Liquidity sweep — price drops below that reaction level, taking out early
                       buyers' stop losses (the 'sweep').
  4. Recovery        — price bounces back with a fresh bullish impulse.
  5. Sellers induced — during the recovery a short bearish pullback forms, trapping
                       sellers who think the move is over.  This IS the zone.
  6. Continuation    — price pushes higher, leaving the inducement zone behind.
  7. RETEST          — price returns into the inducement zone → ENTRY.

Entry  : top of the inducement zone (beginning of the zone).
SL     : bottom of the zone minus buffer  (or HTF range low if nearby).
TP1    : high of the candles that started the initial pullback (wick tops).
TP2    : HTF range high + 5 % of range size.

Bearish case is the exact mirror.
"""

from config import DISPLACEMENT_FACTOR, MIN_RR, INDUCEMENT_SEARCH


def _is_displacement(candle, avg_body):
    body  = abs(float(candle["close"]) - float(candle["open"]))
    rng   = float(candle["high"]) - float(candle["low"])
    if rng == 0 or avg_body == 0:
        return False
    wick_ratio = (rng - body) / rng
    return body >= avg_body * DISPLACEMENT_FACTOR and wick_ratio <= 0.45


def find_inducement_setup(df, htf_bias, htf_range_low, htf_range_high):
    """
    Scan the LTF DataFrame for a complete inducement + sweep entry setup.

    Returns:
        (entry, sl, tp1, tp2, narrative, sweep_price)  on success
        None  when no qualifying setup is found.
    """
    n = len(df)
    if n < 30:
        return None

    df = df.copy().reset_index(drop=True)
    df["body"] = (df["close"] - df["open"]).abs()
    avg_body = df["body"].mean()

    if htf_bias == "BULLISH":
        return _bullish_setup(df, n, avg_body, htf_range_low, htf_range_high)
    if htf_bias == "BEARISH":
        return _bearish_setup(df, n, avg_body, htf_range_low, htf_range_high)
    return None


# ── Bullish ──────────────────────────────────────────────────────────────────

def _bullish_setup(df, n, avg_body, htf_low, htf_high):
    search_from = max(10, n - INDUCEMENT_SEARCH)

    # Iterate from newest sweep candidate backwards so we catch the most recent setup
    for sweep_idx in range(n - 5, search_from, -1):
        candle = df.iloc[sweep_idx]

        # ── Step 3: find a liquidity sweep ───────────────────────────────────
        # Look at the 5-15 candles before for a reaction low that gets swept
        lb = df.iloc[max(0, sweep_idx - 15): sweep_idx]
        if len(lb) < 4:
            continue

        reaction_low = float(lb["low"].min())

        c_low   = float(candle["low"])
        c_close = float(candle["close"])

        # Sweep: wick below reaction low, closes back above it (or next candle does)
        swept = c_low < reaction_low
        recovered = c_close > reaction_low
        if not swept:
            continue
        if not recovered and sweep_idx + 1 < n:
            recovered = float(df["close"].iloc[sweep_idx + 1]) > reaction_low
        if not recovered:
            continue

        # ── Step 1-2: verify a bullish displacement existed before the pullback
        pre_window = df.iloc[max(0, sweep_idx - 25): max(0, sweep_idx - 5)]
        has_impulse = any(
            _is_displacement(pre_window.iloc[i], avg_body) and
            float(pre_window.iloc[i]["close"]) > float(pre_window.iloc[i]["open"])
            for i in range(len(pre_window))
        )
        if not has_impulse:
            continue

        # ── Steps 4-5: find the inducement zone after the sweep ──────────────
        post = df.iloc[sweep_idx + 1: sweep_idx + 25]
        if len(post) < 3:
            continue

        inducement = None
        ind_abs_idx = None

        for j in range(1, len(post) - 2):
            pc   = post.iloc[j]
            prev = post.iloc[j - 1]

            # Inducement candle: bearish, inside an upward recovery
            if float(pc["close"]) >= float(pc["open"]):
                continue                                    # must be bearish
            if float(prev["close"]) <= float(prev["open"]):
                continue                                    # prev must be bullish (recovery)

            # Price must continue upward after the inducement (at least 1 of next 3 candles)
            after = post.iloc[j + 1: j + 4]
            if len(after) < 1:
                continue
            continued_up = float(after["high"].max()) > float(pc["high"])
            if not continued_up:
                continue

            inducement = {
                "high":  float(pc["high"]),
                "low":   float(pc["low"]),
                "open":  float(pc["open"]),
            }
            ind_abs_idx = sweep_idx + 1 + j
            break

        if inducement is None:
            continue

        zone_high = inducement["high"]
        zone_low  = inducement["low"]
        zone_size = zone_high - zone_low

        # ── Step 6: verify price moved above the zone after it formed ────────
        post_ind = df.iloc[ind_abs_idx + 1:]
        if len(post_ind) < 1:
            continue
        if float(post_ind["high"].max()) <= zone_high:
            continue                                        # price never left the zone

        # ── Step 7: current candle is retesting the zone ─────────────────────
        cur_close = float(df["close"].iloc[-1])
        cur_low   = float(df["low"].iloc[-1])

        in_zone      = zone_low <= cur_close <= zone_high * 1.001
        touching     = zone_low * 0.9995 <= cur_low <= zone_high
        if not (in_zone or touching):
            continue

        # Market structure still valid (price above sweep low)
        if cur_close < float(df["low"].iloc[sweep_idx]) * 0.999:
            continue

        # Zone should be in discount (below HTF midpoint)
        if htf_high and htf_low:
            midpoint = (htf_high + htf_low) / 2
            if zone_high > midpoint * 1.001:
                continue

        # ── Targets ──────────────────────────────────────────────────────────
        # TP1: high of the candles that started the initial pullback (wick tops)
        pullback_window = df.iloc[max(0, sweep_idx - 10): sweep_idx + 1]
        tp1 = float(pullback_window["high"].max())

        # TP2: HTF range high + 5 % buffer
        if htf_high and htf_low:
            tp2 = htf_high + (htf_high - htf_low) * 0.05
        else:
            tp2 = tp1 + (tp1 - zone_high) * 0.5

        # ── Entry & SL ───────────────────────────────────────────────────────
        entry   = zone_high                                # top of zone
        sl_base = zone_low - zone_size * 0.5              # 50 % buffer below zone
        # If HTF range low is nearby, use that (whichever is lower = more protection)
        if htf_low and abs(sl_base - htf_low) < zone_size * 3:
            sl = min(sl_base, htf_low - zone_size * 0.2)
        else:
            sl = sl_base

        # Minimum RR filter
        rr = (tp1 - entry) / (entry - sl) if (entry - sl) > 0 else 0
        if rr < MIN_RR:
            continue

        sweep_price = float(df["low"].iloc[sweep_idx])
        narrative = (
            f"Early buyers were induced above {reaction_low:.5f}, "
            f"then their stops were swept down to {sweep_price:.5f}. "
            f"Price recovered with a bullish impulse. "
            f"During that recovery, a short bearish pullback ({zone_low:.5f}–{zone_high:.5f}) "
            f"trapped sellers before price pushed higher — that zone is now being retested. "
            f"HTF structure is bullish. "
            f"Entry at the top of the inducement zone, SL below it. "
            f"TP1 targets the pullback wick highs at {tp1:.5f}. "
            f"TP2 extends to the HTF range high ({tp2:.5f})."
        )

        return (
            round(entry, 5),
            round(sl, 5),
            round(tp1, 5),
            round(tp2, 5),
            narrative,
            sweep_price,
        )

    return None


# ── Bearish (exact mirror) ───────────────────────────────────────────────────

def _bearish_setup(df, n, avg_body, htf_low, htf_high):
    search_from = max(10, n - INDUCEMENT_SEARCH)

    for sweep_idx in range(n - 5, search_from, -1):
        candle = df.iloc[sweep_idx]

        lb = df.iloc[max(0, sweep_idx - 15): sweep_idx]
        if len(lb) < 4:
            continue

        reaction_high = float(lb["high"].max())
        c_high  = float(candle["high"])
        c_close = float(candle["close"])

        swept     = c_high > reaction_high
        recovered = c_close < reaction_high
        if not swept:
            continue
        if not recovered and sweep_idx + 1 < n:
            recovered = float(df["close"].iloc[sweep_idx + 1]) < reaction_high
        if not recovered:
            continue

        pre_window = df.iloc[max(0, sweep_idx - 25): max(0, sweep_idx - 5)]
        has_impulse = any(
            _is_displacement(pre_window.iloc[i], avg_body) and
            float(pre_window.iloc[i]["close"]) < float(pre_window.iloc[i]["open"])
            for i in range(len(pre_window))
        )
        if not has_impulse:
            continue

        post = df.iloc[sweep_idx + 1: sweep_idx + 25]
        if len(post) < 3:
            continue

        inducement = None
        ind_abs_idx = None

        for j in range(1, len(post) - 2):
            pc   = post.iloc[j]
            prev = post.iloc[j - 1]

            # Inducement: bullish candle during bearish recovery
            if float(pc["close"]) <= float(pc["open"]):
                continue
            if float(prev["close"]) >= float(prev["open"]):
                continue

            after = post.iloc[j + 1: j + 4]
            if len(after) < 1:
                continue
            continued_down = float(after["low"].min()) < float(pc["low"])
            if not continued_down:
                continue

            inducement = {
                "high": float(pc["high"]),
                "low":  float(pc["low"]),
                "open": float(pc["open"]),
            }
            ind_abs_idx = sweep_idx + 1 + j
            break

        if inducement is None:
            continue

        zone_high = inducement["high"]
        zone_low  = inducement["low"]
        zone_size = zone_high - zone_low

        post_ind = df.iloc[ind_abs_idx + 1:]
        if len(post_ind) < 1:
            continue
        if float(post_ind["low"].min()) >= zone_low:
            continue

        cur_close = float(df["close"].iloc[-1])
        cur_high  = float(df["high"].iloc[-1])

        in_zone  = zone_low * 0.999 <= cur_close <= zone_high
        touching = zone_low <= cur_high <= zone_high * 1.0005
        if not (in_zone or touching):
            continue

        if cur_close > float(df["high"].iloc[sweep_idx]) * 1.001:
            continue

        # Zone should be in premium (above HTF midpoint)
        if htf_high and htf_low:
            midpoint = (htf_high + htf_low) / 2
            if zone_low < midpoint * 0.999:
                continue

        pullback_window = df.iloc[max(0, sweep_idx - 10): sweep_idx + 1]
        tp1 = float(pullback_window["low"].min())

        if htf_high and htf_low:
            tp2 = htf_low - (htf_high - htf_low) * 0.05
        else:
            tp2 = tp1 - (zone_low - tp1) * 0.5

        entry   = zone_low
        sl_base = zone_high + zone_size * 0.5
        if htf_high and abs(sl_base - htf_high) < zone_size * 3:
            sl = max(sl_base, htf_high + zone_size * 0.2)
        else:
            sl = sl_base

        rr = (entry - tp1) / (sl - entry) if (sl - entry) > 0 else 0
        if rr < MIN_RR:
            continue

        sweep_price = float(df["high"].iloc[sweep_idx])
        narrative = (
            f"Early sellers were induced below {reaction_high:.5f}, "
            f"then their stops were swept up to {sweep_price:.5f}. "
            f"Price recovered with a bearish impulse. "
            f"During that recovery, a short bullish pullback ({zone_low:.5f}–{zone_high:.5f}) "
            f"trapped buyers before price pushed lower — that zone is now being retested. "
            f"HTF structure is bearish. "
            f"Entry at the bottom of the inducement zone, SL above it. "
            f"TP1 targets the pullback wick lows at {tp1:.5f}. "
            f"TP2 extends to the HTF range low ({tp2:.5f})."
        )

        return (
            round(entry, 5),
            round(sl, 5),
            round(tp1, 5),
            round(tp2, 5),
            narrative,
            sweep_price,
        )

    return None
