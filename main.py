"""
main.py — Ron_Market Scanner
Orchestrates HTF bias + LTF inducement entry detection for each symbol.
"""

import time

from config  import SYMBOLS, HTF, LTF, LOOP_DELAY
from data    import get_candles
from structure import determine_bias, check_bos
from entry   import find_inducement_setup
from sessions import in_trading_session
from state   import create_states
from notifier import send_startup, send_htf_update, send_entry_alert


def run():
    send_startup()
    states = create_states(SYMBOLS)

    while True:
        session_active, session_name = in_trading_session()
        print(f"\n{'='*50}")
        print(f"Scan cycle | Session: {session_name} ({'active' if session_active else 'off'})")
        print(f"{'='*50}")

        for symbol in SYMBOLS:
            print(f"\n--- {symbol} ---")
            state = states[symbol]

            # ── 1. HTF DATA & BIAS ────────────────────────────────────────────
            htf_df = get_candles(symbol, HTF, limit=100)
            if htf_df.empty:
                print(f"  No HTF data — skipping {symbol}")
                continue

            # Only recalculate bias when structure has broken (saves noise)
            if check_bos(htf_df, state):
                bias, series, rng_low, rng_high = determine_bias(htf_df)
                state.htf_bias         = bias
                state.htf_series_count = series
                state.htf_range_low    = rng_low
                state.htf_range_high   = rng_high
                state.trade_taken      = False      # new structure resets trade gate
                state.last_entry_zone  = None
                print(f"  Bias updated: {bias} | {series}× series | Range {rng_low:.5f}–{rng_high:.5f}")
                send_htf_update(
                    symbol, HTF,
                    state.htf_bias, state.htf_series_count,
                    state.htf_range_low or 0, state.htf_range_high or 0,
                    session_active, session_name,
                )

            # ── 2. GUARD RAILS ────────────────────────────────────────────────

            if state.htf_bias == "RANGE":
                print(f"  HTF ranging — no trade on {symbol}")
                continue

            if not session_active:
                print(f"  Outside trading session — skipping LTF scan")
                continue

            if state.trade_taken:
                print(f"  Trade already active for {symbol} — waiting for new structure")
                continue

            # ── 3. LTF DATA & ENTRY SCAN ─────────────────────────────────────
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

                # Avoid duplicate alerts on the same zone
                if state.last_entry_zone:
                    prev_low, prev_high = state.last_entry_zone
                    zone_size = prev_high - prev_low
                    if abs(entry - prev_high) < zone_size * 0.5:
                        print(f"  Already alerted on this zone — skipping")
                        continue

                send_entry_alert(
                    symbol, state.htf_bias,
                    entry, sl, tp1, tp2,
                    narrative, sweep_price, session_name,
                )

                state.trade_taken     = True
                state.last_entry_zone = (sl, entry)
                print(f"  Entry alert sent: {entry:.5f} | SL {sl:.5f} | TP1 {tp1:.5f} | TP2 {tp2:.5f}")
            else:
                print(f"  No setup found for {symbol}")

        print(f"\nSleeping {LOOP_DELAY}s...")
        time.sleep(LOOP_DELAY)


if __name__ == "__main__":
    run()
