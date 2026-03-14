import requests
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime
import telegram

API_KEY = os.environ["TWELVE_API_KEY"]
BOT_TOKEN = os.environ["TELEGRAM_TOKEN"]
CHAT_ID = os.environ["CHAT_ID"]

bot = telegram.Bot(token=BOT_TOKEN)

SYMBOLS = ["XAU/USD", "XAG/USD"]
INTERVAL = "3min"

COOLDOWN_MINUTES = 15
last_alert_time = {}

# ---------------- DATA ----------------

def get_data(symbol):

    url = f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={INTERVAL}&outputsize=200&apikey={API_KEY}"

    r = requests.get(url).json()

    df = pd.DataFrame(r["values"])

    df = df.iloc[::-1]

    df["close"] = df["close"].astype(float)
    df["high"] = df["high"].astype(float)
    df["low"] = df["low"].astype(float)

    return df


# ---------------- RSI ----------------

def rsi(series, period=14):

    delta = series.diff()

    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.rolling(period).mean()
    avg_loss = loss.rolling(period).mean()

    rs = avg_gain / avg_loss

    rsi = 100 - (100 / (1 + rs))

    return rsi


# ---------------- PIVOTS ----------------

def pivot_low(series, left=5, right=5):

    pivots = []

    for i in range(left, len(series)-right):

        window = series[i-left:i+right+1]

        if series[i] == min(window):

            pivots.append(i)

    return pivots


def pivot_high(series, left=5, right=5):

    pivots = []

    for i in range(left, len(series)-right):

        window = series[i-left:i+right+1]

        if series[i] == max(window):

            pivots.append(i)

    return pivots


# ---------------- TELEGRAM ----------------

def send(msg):

    bot.send_message(chat_id=CHAT_ID, text=msg)


# ---------------- MAIN ----------------

while True:

    for symbol in SYMBOLS:

        df = get_data(symbol)

        df["rsi"] = rsi(df["close"])

        lows = pivot_low(df["low"])
        highs = pivot_high(df["high"])

        if len(lows) > 1:

            i1 = lows[-2]
            i2 = lows[-1]

            priceLL = df["low"][i2] < df["low"][i1]
            rsiHL = df["rsi"][i2] > df["rsi"][i1]

            if priceLL and rsiHL:

                now = datetime.utcnow()

                if symbol not in last_alert_time or (now - last_alert_time[symbol]).seconds > COOLDOWN_MINUTES*60:

                    entry = df["close"].iloc[-1]
                    sl = df["low"][i2]

                    msg = f"""
🟢 BUY SIGNAL

Symbol: {symbol}

Entry: {entry}
SL: {sl}

RSI Divergence detected
"""

                    send(msg)

                    last_alert_time[symbol] = now


        if len(highs) > 1:

            i1 = highs[-2]
            i2 = highs[-1]

            priceHH = df["high"][i2] > df["high"][i1]
            rsiLH = df["rsi"][i2] < df["rsi"][i1]

            if priceHH and rsiLH:

                now = datetime.utcnow()

                if symbol not in last_alert_time or (now - last_alert_time[symbol]).seconds > COOLDOWN_MINUTES*60:

                    entry = df["close"].iloc[-1]
                    sl = df["high"][i2]

                    msg = f"""
🔴 SELL SIGNAL

Symbol: {symbol}

Entry: {entry}
SL: {sl}

RSI Divergence detected
"""

                    send(msg)

                    last_alert_time[symbol] = now

    time.sleep(180)
