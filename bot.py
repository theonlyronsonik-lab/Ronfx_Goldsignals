import requests
import pandas as pd
import numpy as np
import time
import os
import pytz
from datetime import datetime, timedelta
import telegram

# ENV VARIABLES (SAFE)
API_KEY = os.getenv("d143e9bb8b0c4d7487872fd699280bde")
BOT_TOKEN = os.getenv("7964075094:AAEvEVE2MRke1CXgcoQkr6xqCNf_bzK94J4")
CHAT_ID = os.getenv("6599172354")

bot = telegram.Bot(token=BOT_TOKEN)

SYMBOLS = ["XAU/USD","XAG/USD"]
INTERVAL = "3min"

COOLDOWN = 15  # minutes
last_signal_time = {}

signal_history = []

# SESSION TIMES (UTC)
ASIA = (2,10)
LONDON = (7,16)
NY = (13,22)

# ---------- TELEGRAM ----------

def send(msg):
    try:
        bot.send_message(chat_id=CHAT_ID,text=msg)
    except:
        print("Telegram error")

# ---------- SESSION FILTER ----------

def in_session():

    utc = datetime.utcnow().hour

    if ASIA[0] <= utc <= ASIA[1]:
        return True

    if LONDON[0] <= utc <= LONDON[1]:
        return True

    if NY[0] <= utc <= NY[1]:
        return True

    return False


# ---------- DATA ----------

def get_data(symbol):

    url=f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={INTERVAL}&outputsize=200&apikey={API_KEY}"

    r=requests.get(url).json()

    df=pd.DataFrame(r["values"])

    df=df.iloc[::-1]

    for c in ["open","high","low","close"]:
        df[c]=df[c].astype(float)

    return df


# ---------- RSI ----------

def rsi(series,period=14):

    delta=series.diff()

    gain=delta.clip(lower=0)
    loss=-delta.clip(upper=0)

    avg_gain=gain.rolling(period).mean()
    avg_loss=loss.rolling(period).mean()

    rs=avg_gain/avg_loss

    return 100-(100/(1+rs))


# ---------- PIVOTS ----------

def pivot_low(series,left=5,right=5):

    pivots=[]

    for i in range(left,len(series)-right):

        window=series[i-left:i+right+1]

        if series[i]==min(window):
            pivots.append(i)

    return pivots


def pivot_high(series,left=5,right=5):

    pivots=[]

    for i in range(left,len(series)-right):

        window=series[i-left:i+right+1]

        if series[i]==max(window):
            pivots.append(i)

    return pivots


# ---------- DIVERGENCE ----------

def bullish_divergence(df):

    lows=pivot_low(df["low"])

    if len(lows)<2:
        return False,None

    i1=lows[-2]
    i2=lows[-1]

    priceLL=df["low"][i2] < df["low"][i1]
    rsiHL=df["rsi"][i2] > df["rsi"][i1]

    if priceLL and rsiHL:
        return True,i2

    return False,None


def bearish_divergence(df):

    highs=pivot_high(df["high"])

    if len(highs)<2:
        return False,None

    i1=highs[-2]
    i2=highs[-1]

    priceHH=df["high"][i2] > df["high"][i1]
    rsiLH=df["rsi"][i2] < df["rsi"][i1]

    if priceHH and rsiLH:
        return True,i2

    return False,None


# ---------- DOUBLE SIGNAL LOGIC ----------

signal_stack={}

def double_signal(symbol,signal):

    if symbol not in signal_stack:
        signal_stack[symbol]=[]

    signal_stack[symbol].append(signal)

    if len(signal_stack[symbol])>2:
        signal_stack[symbol].pop(0)

    if signal_stack[symbol]==["BUY","BUY"]:
        return "BUY"

    if signal_stack[symbol]==["SELL","SELL"]:
        return "SELL"

    return None


# ---------- MAIN LOOP ----------

while True:

    try:

        if not in_session():
            time.sleep(60)
            continue

        for symbol in SYMBOLS:

            df=get_data(symbol)

            df["rsi"]=rsi(df["close"])

            bull,idx=bullish_divergence(df)
            bear,idx2=bearish_divergence(df)

            now=datetime.utcnow()

            if symbol in last_signal_time:

                if now-last_signal_time[symbol] < timedelta(minutes=COOLDOWN):
                    continue

            if bull:

                ds=double_signal(symbol,"BUY")

                if ds=="BUY":

                    entry=df["close"].iloc[-1]
                    sl=df["low"][idx]

                    msg=f"""
🟢 BUY SIGNAL

{symbol}

Entry: {entry}
SL: {sl}

RSI Bullish Divergence
"""

                    send(msg)

                    last_signal_time[symbol]=now

                    signal_history.append(("BUY",symbol,entry))

            if bear:

                ds=double_signal(symbol,"SELL")

                if ds=="SELL":

                    entry=df["close"].iloc[-1]
                    sl=df["high"][idx2]

                    msg=f"""
🔴 SELL SIGNAL

{symbol}

Entry: {entry}
SL: {sl}

RSI Bearish Divergence
"""

                    send(msg)

                    last_signal_time[symbol]=now

                    signal_history.append(("SELL",symbol,entry))

        time.sleep(180)

    except Exception as e:

        print("Error:",e)

        time.sleep(60)
