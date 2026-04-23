"""
notifier.py — All Telegram messaging in one place.
"""

import requests
from config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID


def _send(text: str):
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        r = requests.post(
            url,
            data={"chat_id": TELEGRAM_CHAT_ID, "text": text, "parse_mode": "HTML"},
            timeout=10,
        )
        r.raise_for_status()
        print(f"Sent: {text[:80]}...")
    except Exception as exc:
        print(f"Telegram error: {exc}")


def send_startup():
    _send(
        "🤖 <b>Ron_Market Scanner — LIVE</b>\n"
        "Monitoring: XAU/USD | GBP/USD | GBP/JPY | S&P 500\n"
        "Strategy: Inducement + Liquidity Sweep Entry"
    )


def send_htf_update(symbol, timeframe, bias, series_count, htf_low, htf_high, session_active, session_name):
    if bias == "BULLISH":
        emoji  = "🟢"
        series = f"{series_count}× HH/HL"
        strength = "Strong trend" if series_count >= 3 else "Moderate" if series_count == 2 else "Early structure"
    elif bias == "BEARISH":
        emoji  = "🔴"
        series = f"{series_count}× LL/LH"
        strength = "Strong trend" if series_count >= 3 else "Moderate" if series_count == 2 else "Early structure"
    else:
        emoji    = "🟡"
        series   = "No clear series"
        strength = "Ranging — no trade"

    session_line = f"✅ {session_name} session active" if session_active else f"⏸ {session_name} (off-session)"

    _send(
        f"{emoji} <b>HTF UPDATE — {symbol}</b>\n"
        f"Timeframe : {timeframe}\n"
        f"Bias      : <b>{bias}</b>  ({strength})\n"
        f"Series    : {series}\n"
        f"Range     : {htf_low:.5f} – {htf_high:.5f}\n"
        f"Session   : {session_line}"
    )


def send_entry_alert(
    symbol, bias, entry, sl, tp1, tp2,
    narrative, sweep_price, session_name,
    htf_zone_high, htf_zone_low,
):
    direction = "BUY  🟢" if bias == "BULLISH" else "SELL 🔴"
    risk      = abs(entry - sl)
    rr1       = round(abs(tp1 - entry) / risk, 2) if risk > 0 else "—"
    rr2       = round(abs(tp2 - entry) / risk, 2) if risk > 0 else "—"

    _send(
        f"💹 <b>ENTRY ALERT — {symbol}</b>\n"
        f"Direction : <b>{direction}</b>\n"
        f"Session   : {session_name}\n\n"
        f"🏛 <b>HTF Inducement Zone</b> (gate confirmed)\n"
        f"   Zone   : {htf_zone_low:.5f} – {htf_zone_high:.5f}\n"
        f"   Sweep  : {sweep_price:.5f}\n\n"
        f"📍 <b>LTF Entry</b>\n"
        f"   📌 Entry : {entry:.5f}\n"
        f"   🛡  SL   : {sl:.5f}\n"
        f"   🎯 TP1  : {tp1:.5f}   (R:R  {rr1}:1)\n"
        f"   🚀 TP2  : {tp2:.5f}   (R:R  {rr2}:1)\n\n"
        f"📖 <b>Narrative</b>\n{narrative}"
    )

