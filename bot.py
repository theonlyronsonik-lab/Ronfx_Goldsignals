import requests
import pandas as pd
import numpy as np
import time
import os
from datetime import datetime, timedelta
import telegram

API_KEY = os.getenv("d143e9bb8b0c4d7487872fd699280bde")
BOT_TOKEN = os.getenv("7964075094:AAEvEVE2MRke1CXgcoQkr6xqCNf_bzK94J4")
CHAT_ID = os.getenv("6599172354")

if BOT_TOKEN != "":
    bot = telegram.Bot(token=BOT_TOKEN)
else:
    bot = None

SYMBOLS = ["XAU/USD","XAG/USD"]
INTERVAL = "3min"

COOLDOWN_MINUTES = 15

last_signal_time = {}
signal_stack = {}
active_trade = {}
signal_history = []

ASIA = (2,10)
LONDON = (7,16)
NY = (13,22)

# ---------------- TELEGRAM ----------------

def send(msg):

    if bot is None:
        print(msg)
        return

    try:
        bot.send_message(chat_id=CHAT_ID,text=msg)
    except Exception as e:
        print("Telegram error:",e)

# ---------------- SESSION FILTER ----------------

def session_active():

    hour = datetime.utcnow().hour

    if ASIA[0] <= hour <= ASIA[1]:
        return True

    if LONDON[0] <= hour <= LONDON[1]:
        return True

    if NY[0] <= hour <= NY[1]:
        return True

    return False


# ---------------- DATA ----------------

def get_data(symbol):

    url=f"https://api.twelvedata.com/time_series?symbol={symbol}&interval={INTERVAL}&outputsize=200&apikey={API_KEY}"

    r=requests.get(url).json()

    if "values" not in r:
        return None

    df=pd.DataFrame(r["values"])
    df=df.iloc[::-1]

    for c in ["open","high","low","close"]:
        df[c]=df[c].astype(float)

    return df


# ---------------- RSI ----------------

def rsi(series,period=14):

    delta=series.diff()

    gain=delta.clip(lower=0)
    loss=-delta.clip(upper=0)

    avg_gain=gain.rolling(period).mean()
    avg_loss=loss.rolling(period).mean()

    rs=avg_gain/avg_loss

    return 100-(100/(1+rs))


# ---------------- PIVOTS ----------------

def pivot_low(series,left=5,right=5):

    pivots=[]

    for i in range(left,len(series)-right):

        if series[i]==min(series[i-left:i+right+1]):
            pivots.append(i)

    return pivots


def pivot_high(series,left=5,right=5):

    pivots=[]

    for i in range(left,len(series)-right):

        if series[i]==max(series[i-left:i+right+1]):
            pivots.append(i)

    return pivots


# ---------------- DIVERGENCE ----------------

def bullish_div(df):

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


def bearish_div(df):

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


# ---------------- DOUBLE SIGNAL ----------------

def double_confirm(symbol,signal):

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


# ---------------- TAKE PROFIT ----------------

def check_tp(symbol,signal):

    if symbol not in active_trade:
        return

    trade=active_trade[symbol]

    if signal=="BUY" and trade["type"]=="SELL":
        send(f"✅ TP HIT {symbol} (SELL closed)")
        del active_trade[symbol]

    if signal=="SELL" and trade["type"]=="BUY":
        send(f"✅ TP HIT {symbol} (BUY closed)")
        del active_trade[symbol]


# ---------------- MAIN LOOP ----------------

while True:

    try:

        if not session_active():
            time.sleep(60)
            continue

        for symbol in SYMBOLS:

            df=get_data(symbol)

            if df is None:
                continue

            df["rsi"]=rsi(df["close"])

            bull,idx=bullish_div(df)
            bear,idx2=bearish_div(df)

            now=datetime.utcnow()

            if symbol in last_signal_time:

                if now-last_signal_time[symbol] < timedelta(minutes=COOLDOWN_MINUTES):
                    continue

            if bull:

                check_tp(symbol,"BUY")

                ds=double_confirm(symbol,"BUY")

                if ds=="BUY":

                    entry=df["close"].iloc[-1]
                    sl=df["low"][idx]

                    send(f"""
🟢 BUY SIGNAL
{symbol}

Entry: {entry}
SL: {sl}
""")

                    active_trade[symbol]={"type":"BUY","entry":entry}

                    last_signal_time[symbol]=now


            if bear:

                check_tp(symbol,"SELL")

                ds=double_confirm(symbol,"SELL")

                if ds=="SELL":

                    entry=df["close"].iloc[-1]
                    sl=df["high"][idx2]

                    send(f"""
🔴 SELL SIGNAL
{symbol}

Entry: {entry}
SL: {sl}
""")

                    active_trade[symbol]={"type":"SELL","entry":entry}

                    last_signal_time[symbol]=now

        time.sleep(180)

    except Exception as e:

        print("Runtime error:",e)

        time.sleep(60)
