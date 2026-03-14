# file: rsi_divergence_bot.py
import requests
import pandas as pd
import time
import numpy as np
from datetime import datetime, timezone, timedelta
import telegram

# -------------------- CONFIG --------------------
API_KEY = "YOUR_TWELVE_DATA_API_KEY"
SYMBOLS = ["XAU/USD", "XAG/USD"]  # Gold & Silver
INTERVAL = "3min"
RSI_PERIOD = 14
LB_L = 5
LB_R = 5
RANGE_LOWER = 5
RANGE_UPPER = 60
COOLDOWN_MINUTES = 15

TELEGRAM_TOKEN = "7964075094:AAEvEVE2MRke1CXgcoQkr6xqCNf_bzK94J4"
CHAT_ID = 6599172354

bot = telegram.Bot(token=TELEGRAM_TOKEN)

# -------------------- FUNCTIONS --------------------
def fetch_candles(symbol):
    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={INTERVAL}&outputsize=200&apikey={API_KEY}"
    resp = requests.get(url).json()
    if "values" not in resp:
        print(f"Error fetching data for {symbol}: {resp}")
        return None
    df = pd.DataFrame(resp["values"])
    df = df.iloc[::-1]  # oldest first
    df['datetime'] = pd.to_datetime(df['datetime'])
    for col in ['open', 'high', 'low', 'close']:
        df[col] = df[col].astype(float)
    return df.reset_index(drop=True)

def compute_rsi(series, period=14):
    delta = series.diff()
    up = delta.clip(lower=0)
    down = -delta.clip(upper=0)
    ma_up = up.ewm(span=period, adjust=False).mean()
    ma_down = down.ewm(span=period, adjust=False).mean()
    rsi = 100 - (100 / (1 + ma_up / ma_down))
    return rsi

def pivot_low(df, lbL, lbR):
    lows = df['low'].values
    pl = [False]*len(df)
    for i in range(lbL, len(df)-lbR):
        if lows[i] == min(lows[i-lbL:i+lbR+1]):
            pl[i] = True
    return pl

def pivot_high(df, lbL, lbR):
    highs = df['high'].values
    ph = [False]*len(df)
    for i in range(lbL, len(df)-lbR):
        if highs[i] == max(highs[i-lbL:i+lbR+1]):
            ph[i] = True
    return ph

def _in_range(bars_since, lower, upper):
    return lower <= bars_since <= upper

def send_telegram(message):
    try:
        bot.send_message(chat_id=CHAT_ID, text=message)
    except Exception as e:
        print("Telegram send error:", e)

# -------------------- MAIN LOOP --------------------
last_signal = {"XAU/USD": None, "XAG/USD": None}
last_signal_time = {"XAU/USD": None, "XAG/USD": None}
current_trade = {"XAU/USD": None, "XAG/USD": None}

while True:
    for symbol in SYMBOLS:
        df = fetch_candles(symbol)
        if df is None:
            continue

        df['rsi'] = compute_rsi(df['close'], RSI_PERIOD)
        df['pl'] = pivot_low(df, LB_L, LB_R)
        df['ph'] = pivot_high(df, LB_L, LB_R)

        bars_since_last_pl = df['pl'][::-1].cumsum()  # rough bar count
        bars_since_last_ph = df['ph'][::-1].cumsum()

        last_idx = len(df)-1

        # ---------------- SIGNAL LOGIC ----------------
        # Bull signal
        if last_idx >= LB_R+1:
            # Regular Bullish
            inrange_pl = _in_range(1, RANGE_LOWER, RANGE_UPPER)
            oscHL = df['rsi'].iloc[last_idx-LB_R] > df['rsi'].iloc[:last_idx-LB_R].max()
            priceLL = df['low'].iloc[last_idx-LB_R] < df['low'].iloc[:last_idx-LB_R].min()
            bull_signal = df['pl'].iloc[last_idx] and oscHL and priceLL

            # Regular Bearish
            inrange_ph = _in_range(1, RANGE_LOWER, RANGE_UPPER)
            oscLH = df['rsi'].iloc[last_idx-LB_R] < df['rsi'].iloc[:last_idx-LB_R].min()
            priceHH = df['high'].iloc[last_idx-LB_R] > df['high'].iloc[:last_idx-LB_R].max()
            bear_signal = df['ph'].iloc[last_idx] and oscLH and priceHH

            now = datetime.utcnow()
            cooldown = last_signal_time[symbol] is not None and (now - last_signal_time[symbol]).total_seconds() < COOLDOWN_MINUTES*60

            # Double signal entry
            if bull_signal and last_signal[symbol] == "BULL" and not cooldown and current_trade[symbol] is None:
                entry_price = df['close'].iloc[last_idx]
                sl = df['low'].iloc[last_idx-LB_R]
                current_trade[symbol] = {"type":"BUY","entry":entry_price,"sl":sl,"tp":None}
                message = f"{symbol} → BUY Signal\nEntry: {entry_price}\nSL: {sl}\nCooldown: {COOLDOWN_MINUTES}min"
                send_telegram(message)
                last_signal_time[symbol] = now

            if bear_signal and last_signal[symbol] == "BEAR" and not cooldown and current_trade[symbol] is None:
                entry_price = df['close'].iloc[last_idx]
                sl = df['high'].iloc[last_idx-LB_R]
                current_trade[symbol] = {"type":"SELL","entry":entry_price,"sl":sl,"tp":None}
                message = f"{symbol} → SELL Signal\nEntry: {entry_price}\nSL: {sl}\nCooldown: {COOLDOWN_MINUTES}min"
                send_telegram(message)
                last_signal_time[symbol] = now

            # Close trades (TP)
            if current_trade[symbol]:
                trade = current_trade[symbol]
                if trade["type"] == "BUY" and bear_signal:
                    trade["tp"] = df['close'].iloc[last_idx]
                    message = f"{symbol} → BUY Closed (TP)\nEntry: {trade['entry']}\nSL: {trade['sl']}\nTP: {trade['tp']}"
                    send_telegram(message)
                    current_trade[symbol] = None
                    last_signal_time[symbol] = now
                if trade["type"] == "SELL" and bull_signal:
                    trade["tp"] = df['close'].iloc[last_idx]
                    message = f"{symbol} → SELL Closed (TP)\nEntry: {trade['entry']}\nSL: {trade['sl']}\nTP: {trade['tp']}"
                    send_telegram(message)
                    current_trade[symbol] = None
                    last_signal_time[symbol] = now

            # Update last signal
            if bull_signal:
                last_signal[symbol] = "BULL"
            if bear_signal:
                last_signal[symbol] = "BEAR"

    time.sleep(180)  # wait 3 minutes for next candle
