# rsi_divergence_bot.py
import requests
import pandas as pd
import time
import numpy as np
from datetime import datetime
import telegram
import os

# -------------------- CONFIG (from env) --------------------
API_KEY = os.getenv("d143e9bb8b0c4d7487872fd699280bde")
SYMBOLS = ["XAU/USD", "XAG/USD"]
INTERVAL = "3min"
RSI_PERIOD = 14
LB_L = 5
LB_R = 5
RANGE_LOWER = 5
RANGE_UPPER = 60
COOLDOWN_MINUTES = 15

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = int(os.getenv("TELEGRAM_CHAT_ID"))

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
last_signal = {symbol: None for symbol in SYMBOLS}
last_signal_time = {symbol: None for symbol in SYMBOLS}
current_trade = {symbol: None for symbol in SYMBOLS}

while True:
    for symbol in SYMBOLS:
        df = fetch_candles(symbol)
        if df is None:
            continue

        df['rsi'] = compute_rsi(df['close'], RSI_PERIOD)
        df['pl'] = pivot_low(df, LB_L, LB_R)
        df['ph'] = pivot_high(df, LB_L, LB_R)

        last_idx = len(df)-1
        now = datetime.utcnow()
        cooldown = last_signal_time[symbol] and (now - last_signal_time[symbol]).total_seconds() < COOLDOWN_MINUTES*60

        # ---------------- SIGNAL LOGIC ----------------
        if last_idx >= LB_R+1:
            # Regular Bullish
            bull_signal = df['pl'].iloc[last_idx] and df['rsi'].iloc[last_idx-LB_R] > df['rsi'].iloc[:last_idx-LB_R].max() and df['low'].iloc[last_idx-LB_R] < df['low'].iloc[:last_idx-LB_R].min()
            # Regular Bearish
            bear_signal = df['ph'].iloc[last_idx] and df['rsi'].iloc[last_idx-LB_R] < df['rsi'].iloc[:last_idx-LB_R].min() and df['high'].iloc[last_idx-LB_R] > df['high'].iloc[:last_idx-LB_R].max()

            # Double signal entry
            if bull_signal and last_signal[symbol] == "BULL" and not cooldown and current_trade[symbol] is None:
                entry_price = df['close'].iloc[last_idx]
                sl = df['low'].iloc[last_idx-LB_R]
                current_trade[symbol] = {"type":"BUY","entry":entry_price,"sl":sl,"tp":None}
                send_telegram(f"{symbol} → BUY Signal\nEntry: {entry_price}\nSL: {sl}\nCooldown: {COOLDOWN_MINUTES}min")
                last_signal_time[symbol] = now
