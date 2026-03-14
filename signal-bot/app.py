from flask import Flask, request, jsonify
import requests
from datetime import datetime, timedelta, time

TELEGRAM_TOKEN = "YOUR_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

COOLDOWN = 15

ASIA = (time(2,0), time(10,0))
LONDON = (time(7,0), time(16,0))
NEWYORK = (time(13,0), time(22,0))

last_signal = None
current_trade = None
last_alert = datetime.min

app = Flask(__name__)

def send_telegram(msg):

    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"

    requests.post(url,json={
        "chat_id": CHAT_ID,
        "text": msg
    })

def session_active():

    now = datetime.utcnow().time()

    sessions = [ASIA,LONDON,NEWYORK]

    for s,e in sessions:
        if s <= now <= e:
            return True

    return False

def cooldown():

    return datetime.utcnow() < last_alert + timedelta(minutes=COOLDOWN)

def process(signal):

    global last_signal,current_trade,last_alert

    if not session_active():
        return

    if cooldown():
        return

    if signal == last_signal:

        if current_trade is None:

            if signal == "BULL":
                current_trade = "BUY"
                send_telegram("📈 BUY XAU/XAG\nBULL + BULL")

            if signal == "BEAR":
                current_trade = "SELL"
                send_telegram("📉 SELL XAU/XAG\nBEAR + BEAR")

            last_alert = datetime.utcnow()

        else:

            if current_trade == "BUY" and signal == "BEAR":
                send_telegram("✅ CLOSE BUY\nBEAR + BEAR")
                current_trade = None
                last_alert = datetime.utcnow()

            if current_trade == "SELL" and signal == "BULL":
                send_telegram("✅ CLOSE SELL\nBULL + BULL")
                current_trade = None
                last_alert = datetime.utcnow()

    last_signal = signal

@app.route("/signal",methods=["POST"])
def signal():

    data = request.json
    signal = data.get("signal")

    process(signal)

    return jsonify({"ok":True})

app.run(host="0.0.0.0",port=5000)
