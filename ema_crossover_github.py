import ccxt
import pandas as pd
import time
from datetime import datetime

# ======================
# Settings
# ======================
symbols_to_check = [
    "KOMA/USDT", "DOGS/USDT", "NEIROETH/USDT", "1000RATS/USDT", "ORDI/USDT",
    "MEME/USDT", "PIPPIN/USDT", "BAN/USDT", "1000SHIB/USDT", "OM/USDT",
    "CHILLGUY/USDT", "PONKE/USDT", "BOME/USDT", "MYRO/USDT", "PEOPLE/USDT",
    "PENGU/USDT", "SPX/USDT", "1000BONK/USDT", "PNUT/USDT", "FARTCOIN/USDT",
    "HIPPO/USDT", "AIXBT/USDT", "BRETT/USDT", "VINE/USDT", "MOODENG/USDT",
    "MUBARAK/USDT", "MEW/USDT", "POPCAT/USDT", "1000FLOKI/USDT", "DOGE/USDT",
    "1000CAT/USDT", "ACT/USDT", "SLERF/USDT", "DEGEN/USDT", "WIF/USDT",
    "1000PEPE/USDT"
]

exchange = ccxt.binance()

# ======================
# EMA Calculation
# ======================
def fetch_ohlcv(symbol, timeframe="15m", limit=100):
    try:
        return exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    except Exception as e:
        print(f"⚠️ Error fetching {symbol}: {e}")
        return None

def calculate_ema(df, period):
    return df["close"].ewm(span=period, adjust=False).mean()

# ======================
# Strategy Check
# ======================
def check_signal(symbol):
    ohlcv = fetch_ohlcv(symbol)
    if ohlcv is None:
        return None
    
    df = pd.DataFrame(ohlcv, columns=["time", "open", "high", "low", "close", "volume"])
    df["EMA9"] = calculate_ema(df, 9)
    df["EMA21"] = calculate_ema(df, 21)
    
    if df["EMA9"].iloc[-2] < df["EMA21"].iloc[-2] and df["EMA9"].iloc[-1] > df["EMA21"].iloc[-1]:
        return "BUY"
    elif df["EMA9"].iloc[-2] > df["EMA21"].iloc[-2] and df["EMA9"].iloc[-1] < df["EMA21"].iloc[-1]:
        return "SELL"
    else:
        return None

# ======================
# Main Runner
# ======================
def run_once():
    print(f"\n===== New Scan at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC =====")
    
    for symbol in symbols_to_check:
        signal = check_signal(symbol)
        if signal:
            print(f"✅ {symbol}: {signal}")
        else:
            print(f"– {symbol}: No signal")

# ======================
# Entry Point (run once only)
# ======================
if __name__ == "__main__":
    run_once()
