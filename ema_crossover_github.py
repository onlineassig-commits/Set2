import os
import ccxt
import pandas as pd
from datetime import datetime, timezone
import requests

# === Config ===
symbols = [
    "1000RATS/USDT:USDT", "1000SHIB/USDT:USDT", "1000BONK/USDT:USDT",
    "1000FLOKI/USDT:USDT", "1000CAT/USDT:USDT", "1000PEPE/USDT:USDT"
]

exchanges_to_check = [
    'bybit','okx','gateio','kucoin','huobi','coinex',
    'binanceusdm','kraken','phemex','bitget'
]

timeframe = "2h"
ema_fast, ema_slow = 12, 50
max_age_minutes = 150  # only use candles <= 150 minutes old

# === Helpers ===
def get_ema(df, length):
    return df['close'].ewm(span=length, adjust=False).mean()

def fetch_candles(exchange, symbol, tf="2h", limit=100):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["time","open","high","low","close","volume"])
        df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
        return df
    except Exception:
        return pd.DataFrame()

def minutes_ago(ts):
    now = datetime.now(timezone.utc)
    diff = now - ts
    return int(diff.total_seconds() // 60)

# === Main Logic ===
def evaluate(symbol):
    signal = None
    details = []

    for ex_id in exchanges_to_check:
        try:
            ex_class = getattr(ccxt, ex_id)
            exchange = ex_class({'options': {'defaultType':'future'}})
            if not exchange.has.get("fetchOHLCV", False):
                continue

            df = fetch_candles(exchange, symbol, tf=timeframe, limit=100)
            if df.empty:
                continue

            df["ema12"] = get_ema(df, ema_fast)
            df["ema50"] = get_ema(df, ema_slow)

            last = df.iloc[-1]
            mins = minutes_ago(last["time"])
            if mins > max_age_minutes:
                continue

            # Short-only condition (relaxed)
            if last["ema12"] < last["ema50"]:
                signal = f"{symbol} ({ex_id.upper()}) @ {last['close']:.6f} | EMA12={last['ema12']:.4f}, EMA50={last['ema50']:.4f}"
                details.append(signal)
                break  # Stop after first exchange providing data

        except Exception:
            continue

    if not details:
        details.append(f"{symbol} not available on any exchange")
    return details

def main():
    all_details = []

    for sym in symbols:
        det = evaluate(sym)
        all_details.extend(det)

    # Print results
    print("=== COIN DATA CHECK ===")
    for d in all_details:
        print(d)

    # Send to Telegram
    tg_token = os.getenv("TELEGRAM_TOKEN")
    tg_chat = os.getenv("TELEGRAM_CHAT_ID")
    if tg_token and tg_chat:
        try:
            url = f"https://api.telegram.org/bot{tg_token}/sendMessage"
            message = "\n".join(all_details)
            # Telegram has a 4096 character limit per message
            if len(message) > 4000:
                message = message[:4000] + "\n[Message truncated]"
            requests.post(url, data={"chat_id": tg_chat, "text": message}, timeout=10)
            print("✅ Sent to Telegram")
        except Exception as e:
            print("Telegram failed:", e)

if __name__ == "__main__":
    main()
