"""
main.py — Ron_Market Scanner
Orchestrates HTF bias + LTF inducement entry detection for each symbol.

Scanning strategy:
  - Scanning is restricted to London (06:00–11:00 UTC) and New York
    (11:00–17:00 UTC) trading sessions only.  Off-session the bot sleeps
    without making any API calls, keeping usage well within rate limits.
  - When a session is active, HTF and LTF are scanned every cycle and
    setups are tracked in state as they form (with timestamps).
  - A signal is only sent when ALL four conditions are simultaneously true:
      1. HTF inducement zone is complete.
      2. LTF entry setup is found and valid.
      3. HTF zone and LTF entry correlate (LTF entry sits inside HTF zone).
      4. Bot is inside an active trading session (London or New York).
  - If any condition is unmet the bot prints a "Waiting for…" message and
    keeps scanning — no alert is fired.
"""

import time
from datetime import datetime, timezone

from config    import SYMBOLS, HTF, LTF, LOOP_DELAY
from data      import get_candles
from structure import determine_bias, check_bos
from entry     import find_inducement_setup, find_htf_inducement
from sessions  import in_trading_session
from state     import create_states
from notifier  import send_startup, send_htf_update, send_entry_alert


def _check_correlation(htf_inducement, ltf_setup, htf_bias):
    """
    Return True when the LTF entry price aligns with the HTF inducement zone.

    Bullish: LTF entry (zone top) must sit at or below the HTF zone high,
             and at or above the HTF zone low (with a small 0.5 % tolerance).
    Bearish: LTF entry (zone bottom) must sit at or above the HTF zone low,
             and at or below the HTF zone high (with a small 0.5 % tolerance).

    A 0.5 % tolerance is applied so that entries that are marginally outside
    the HTF zone (due to timeframe granularity) are still accepted.
    """
    if htf_inducement is None or ltf_setup is None:
        return False

    htf_zone_high, htf_zone_low, _, _ = htf_inducement
    entry = ltf_setup[0]   # first element of the setup tuple
    tolerance = (htf_zone_high - htf_zone_low) * 0.5   # 50 % of zone width

    if htf_bias == "BULLISH":
        return (htf_zone_low - tolerance) <= entry <= (htf_zone_high + tolerance)
    if htf_bias == "BEARISH":
        return (htf_zone_low - tolerance) <= entry <= (htf_zone_high + tolerance)
    return False


def run():
    send_startup()
    states = create_states(SYMBOLS)

    while True:
        now = datetime.now(timezone.utc)
        session_active, session_name = in_trading_session()
        print(f"\n{'='*50}")
        print(f"Scan cycle | {now.strftime('%Y-%m-%d %H:%M:%S')} UTC | "
              f"Session: {session_name} ({'active' if session_active else 'off'})")
        print(f"{'='*50}")

        # ── SESSION GATE ──────────────────────────────────────────────────────
        # Skip all API calls when outside London / New York sessions.
        # This is the primary rate-limit guard: no network requests are made
        # off-session.  The bot simply sleeps and re-checks next cycle.
        if not session_active:
            print(f"  Off-session ({session_name}) — sleeping, no API calls made")
            print(f"\nSleeping {LOOP_DELAY}s...")
            time.sleep(LOOP_DELAY)
            continue

        for symbol in SYMBOLS:
            print(f"\n--- {symbol} ---")
            state = states[symbol]

            # ── 1. HTF DATA & BIAS ────────────────────────────────────────────
            htf_df = get_candles(symbol, HTF, limit=100)
            if htf_df.empty:
                print(f"  No HTF data — skipping {symbol}")
                continue

            # Only recalculate bias when structure has broken (saves noise).
            # On BOS, reset all tracked setups so stale data never leaks into
            # the next structure cycle.
            if check_bos(htf_df, state):
                bias, series, rng_low, rng_high = determine_bias(htf_df)
                state.htf_bias                 = bias
                state.htf_series_count         = series
                state.htf_range_low            = rng_low
                state.htf_range_high           = rng_high
                state.last_alerted_setup       = None
                state.htf_inducement           = None
                state.htf_inducement_complete  = False
                state.htf_inducement_timestamp = None
                state.ltf_setup                = None
                state.ltf_setup_timestamp      = None
                state.setup_correlation_valid  = False
                print(f"  Bias updated: {bias} | {series}× series | Range {rng_low:.5f}–{rng_high:.5f}")
                send_htf_update(
                    symbol, HTF,
                    state.htf_bias, state.htf_series_count,
                    state.htf_range_low or 0, state.htf_range_high or 0,
                    session_active, session_name,
                )

            # ── 2. RANGE GUARD ────────────────────────────────────────────────
            if state.htf_bias == "RANGE":
                print(f"  HTF ranging — no trade on {symbol}")
                continue

            # ── 3. HTF INDUCEMENT SCAN ────────────────────────────────────────
            # Re-scan every cycle so the gate updates if a newer zone forms.
            # Timestamp is only set the first time a zone is detected; it is
            # preserved across cycles so we know when the zone originally formed.
            htf_ind = find_htf_inducement(htf_df, state.htf_bias)
            if htf_ind is not None:
                if state.htf_inducement != htf_ind:
                    # New or updated zone — record the discovery time
                    state.htf_inducement_timestamp = now
                state.htf_inducement          = htf_ind
                state.htf_inducement_complete = True
                htf_zone_high, htf_zone_low, htf_sweep, _ = htf_ind
                print(
                    f"  HTF inducement complete: zone {htf_zone_low:.5f}–{htf_zone_high:.5f} "
                    f"| sweep {htf_sweep:.5f} "
                    f"| found {state.htf_inducement_timestamp.strftime('%H:%M:%S')} UTC"
                )
            else:
                state.htf_inducement_complete = False
                print(f"  HTF inducement not yet complete — tracking")

            # ── 4. LTF DATA & SETUP SCAN ─────────────────────────────────────
            ltf_df = get_candles(symbol, LTF, limit=100)
            if ltf_df.empty:
                print(f"  No LTF data — skipping {symbol}")
                continue

            setup = find_inducement_setup(
                ltf_df,
                state.htf_bias,
                state.htf_range_low,
                state.htf_range_high,
            )

            if setup:
                entry, sl, tp1, tp2, narrative, sweep_price = setup
                if state.ltf_setup != (entry, sl, tp1, tp2):
                    # New or updated setup — record the discovery time
                    state.ltf_setup_timestamp = now
                state.ltf_setup = (entry, sl, tp1, tp2, narrative, sweep_price)
                print(
                    f"  LTF setup tracked: entry {entry:.5f} | SL {sl:.5f} "
                    f"| found {state.ltf_setup_timestamp.strftime('%H:%M:%S')} UTC"
                )
            else:
                # No setup visible this cycle — clear stale data
                if state.ltf_setup is not None:
                    print(f"  LTF setup no longer valid — clearing")
                    state.ltf_setup           = None
                    state.ltf_setup_timestamp = None
                    state.setup_correlation_valid = False
                else:
                    print(f"  No LTF setup found — tracking")

            # ── 5. CORRELATION CHECK ──────────────────────────────────────────
            # Evaluate whether the LTF entry sits inside the HTF zone.
            if state.htf_inducement_complete and state.ltf_setup is not None:
                state.setup_correlation_valid = _check_correlation(
                    state.htf_inducement, state.ltf_setup, state.htf_bias
                )
                if state.setup_correlation_valid:
                    print(f"  Correlation: ✅ HTF zone and LTF entry align")
                else:
                    print(f"  Correlation: ❌ HTF zone and LTF entry do NOT align")
            else:
                state.setup_correlation_valid = False

            # ── 6. SIGNAL GATE ────────────────────────────────────────────────
            # All four conditions must be true before a signal is sent.
            cond_htf     = state.htf_inducement_complete
            cond_ltf     = state.ltf_setup is not None
            cond_corr    = state.setup_correlation_valid
            cond_session = session_active

            if not (cond_htf and cond_ltf and cond_corr and cond_session):
                reasons = []
                if not cond_htf:
                    reasons.append("HTF inducement incomplete")
                if not cond_ltf:
                    reasons.append("no LTF setup")
                if not cond_corr:
                    reasons.append("structures not correlated")
                if not cond_session:
                    reasons.append(f"off-session ({session_name})")
                print(f"  ⏳ Waiting for: {' | '.join(reasons)}")
                continue

            # All conditions met — check deduplication before firing
            entry, sl, tp1, tp2, narrative, sweep_price = state.ltf_setup
            htf_zone_high, htf_zone_low, htf_sweep, htf_ind_narrative = state.htf_inducement

            if state.last_alerted_setup == (entry, sl):
                print(f"  Setup already alerted (entry {entry:.5f} / SL {sl:.5f}) — skipping duplicate")
                continue

            # ── 7. SEND SIGNAL ────────────────────────────────────────────────
            send_entry_alert(
                symbol          = symbol,
                bias            = state.htf_bias,
                entry           = entry,
                sl              = sl,
                tp1             = tp1,
                tp2             = tp2,
                narrative       = narrative,
                sweep_price     = sweep_price,
                session_name    = session_name,
                htf_zone_high   = htf_zone_high,
                htf_zone_low    = htf_zone_low,
                htf_narrative   = htf_ind_narrative,
                htf_found_at    = state.htf_inducement_timestamp,
                ltf_found_at    = state.ltf_setup_timestamp,
                signal_sent_at  = now,
            )

            state.last_alerted_setup = (entry, sl)
            print(
                f"  ✅ Signal sent: entry {entry:.5f} | SL {sl:.5f} "
                f"| TP1 {tp1:.5f} | TP2 {tp2:.5f}"
            )

        print(f"\nSleeping {LOOP_DELAY}s...")
        time.sleep(LOOP_DELAY)


if __name__ == "__main__":
    run()
