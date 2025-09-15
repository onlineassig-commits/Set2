# ema_crossover_15m_relaxed.py
# Single timeframe EMA: 15m (9/16/200)
# Relaxed rules: current trend mode + price filter + lookback window

import os
import ccxt
import pandas as pd
import requests
from datetime import datetime, timezone
from tqdm import tqdm
import time

# === Config ===
symbols = [
    "KOMA/USDT:USDT","DOGS/USDT:USDT","NEIRO/USDT:USDT",
    "ORDI/USDT:USDT","MEME/USDT:USDT","PIPPIN/USDT:USDT","BAN/USDT:USDT",
    "OM/USDT:USDT","CHILLGUY/USDT:USDT","PONKE/USDT:USDT",
    "BOME/USDT:USDT","MYRO/USDT:USDT","PEOPLE/USDT:USDT","PENGU/USDT:USDT",
    "SPX/USDT:USDT","PNUT/USDT:USDT","FARTCOIN/USDT:USDT",
    "HIPPO/USDT:USDT","AIXBT/USDT:USDT","BRETT/USDT:USDT","VINE/USDT:USDT",
    "MOODENG/USDT:USDT","MUBARAK/USDT:USDT","MEW/USDT:USDT","POPCAT/USDT:USDT",
    "DOGE/USDT:USDT","ACT/USDT:USDT",
    "SLERF/USDT:USDT","DEGEN/USDT:USDT","WIF/USDT:USDT"
]

primary_exchanges = ['binanceusdm','bybit','okx']
secondary_exchanges = ['gateio','kucoin','huobi','coinex','kraken','phemex','bitget']

# EMA settings
ema_fast, ema_slow, ema_long = 9, 16, 200
max_age_minutes = 150
lookback_candles = 5
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT = os.getenv("TELEGRAM_CHAT_ID")
TELEGRAM_API = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage" if TELEGRAM_TOKEN else None
TG_MAX = 4000

# === Helpers ===
def get_ema(df, length):
    return df['close'].ewm(span=length, adjust=False).mean()

def fetch_candles(exchange, symbol, tf="15m", limit=200):
    try:
        ohlcv = exchange.fetch_ohlcv(symbol, tf, limit=limit)
        df = pd.DataFrame(ohlcv, columns=["time","open","high","low","close","volume"])
        df["time"] = pd.to_datetime(df["time"], unit="ms", utc=True)
        return df
    except Exception:
        return pd.DataFrame()

def minutes_ago(ts):
    now = datetime.now(timezone.utc)
    return int((now - ts).total_seconds() // 60)

def send_telegram_text_chunks(text):
    if not TELEGRAM_API or not TELEGRAM_CHAT:
        print("Telegram not configured.")
        return
    lines = text.splitlines()
    chunks, cur = [], ""
    for line in lines:
        if len(cur) + len(line) + 1 <= TG_MAX:
            cur += line + "\n"
        else:
            if cur: chunks.append(cur)
            cur = line + "\n"
    if cur: chunks.append(cur)
    for chunk in chunks:
        try:
            requests.post(TELEGRAM_API, data={"chat_id": TELEGRAM_CHAT, "text": chunk}, timeout=15)
            time.sleep(0.4)
        except Exception as e:
            print("Telegram send failed:", e)

# === Evaluation ===
def evaluate(symbol):
    details = []
    exchanges_to_check = primary_exchanges + secondary_exchanges
    for ex_id in exchanges_to_check:
        try:
            ex_class = getattr(ccxt, ex_id)
            exchange = ex_class({'options': {'defaultType':'future'}})
            if not exchange.has.get("fetchOHLCV", False):
                continue

            # 15m chart
            df = fetch_candles(exchange, symbol, tf="15m", limit=200)
            if df.empty: 
                continue

            df["ema9"] = get_ema(df, ema_fast)
            df["ema16"] = get_ema(df, ema_slow)
            df["ema200"] = get_ema(df, ema_long)

            last = df.iloc[-1]

            if minutes_ago(last["time"]) > max_age_minutes:
                continue

            # Relaxed rule: EMA9 below EMA16 (trend mode)
            ema_condition = last["ema9"] < last["ema16"]

            # Lookback rule: crossover happened within last N candles
            cross_recent = False
            for i in range(1, lookback_candles+1):
                prev = df.iloc[-(i+1)]
                curr = df.iloc[-i]
                if prev["ema9"] >= prev["ema16"] and curr["ema9"] < curr["ema16"]:
                    cross_recent = True
                    break

            # Trend filter: price < EMA200
            trend_ok = last["close"] < last["ema200"]

            # Final signal
            bearish_signal = ema_condition and cross_recent and trend_ok
            tag = "✅ Strong" if bearish_signal else ""

            signal = f"SHORT SIGNAL: {symbol} ({ex_id.upper()}) @ {last['close']:.6f} | {tag}" if bearish_signal else None

            details.append(
                f"{symbol} ({ex_id.upper()}) @ {last['close']:.6f} | "
                f"EMA9={last['ema9']:.4f}, EMA16={last['ema16']:.4f}, EMA200={last['ema200']:.4f} "
                f"| ema_condition={'YES' if ema_condition else 'NO'}, cross_recent={'YES' if cross_recent else 'NO'}, price<200={'YES' if trend_ok else 'NO'} {tag}"
            )

            return signal, details, False

        except Exception:
            continue

    return None, [f"{symbol} not available on any exchange"], True

# === Main ===
def main():
    signals, details_all, missing = [], [], []
    total, processed, strong_count = len(symbols), 0, 0

    for sym in tqdm(symbols, desc="Checking coins", unit="coin"):
        sig, det, is_missing = evaluate(sym)
        details_all.extend(det)
        if is_missing:
            missing.append(sym)
        else:
            processed += 1
        if sig:
            signals.append(sig)
            strong_count += 1

    # Telegram message
    lines = ["=== SHORT SIGNALS (15m EMA relaxed crossover) ==="]
    lines.extend(signals if signals else ["No valid short signals this run."])
    lines.append("\n=== MISSING COINS ===")
    lines.extend(missing if missing else ["None"])
    lines.append(f"\n=== SUMMARY ===\nChecked: {total} | Processed: {processed} | Missing: {len(missing)} | "
                 f"Signals: {len(signals)} (Strong: {strong_count})")
    final_text = "\n".join(lines)
    send_telegram_text_chunks(final_text)
    print(final_text)

if __name__ == "__main__":
    main()
