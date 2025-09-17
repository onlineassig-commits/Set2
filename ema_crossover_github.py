import ccxt
import pandas as pd
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
# Indicator Functions
# ======================
def get_atr(df, period=7):
    df['H-L'] = df['high'] - df['low']
    df['H-PC'] = (df['high'] - df['close'].shift()).abs()
    df['L-PC'] = (df['low'] - df['close'].shift()).abs()
    df['TR'] = df[['H-L', 'H-PC', 'L-PC']].max(axis=1)
    df['ATR'] = df['TR'].rolling(period).mean()
    return df['ATR']

def get_supertrend(df, atr_period=7, multiplier=2.0):
    """
    Fast-responding Supertrend
    """
    hl2 = (df['high'] + df['low']) / 2
    atr = get_atr(df, atr_period)

    # Basic bands
    upperband = hl2 + (multiplier * atr)
    lowerband = hl2 - (multiplier * atr)

    # Final bands
    final_upperband = upperband.copy()
    final_lowerband = lowerband.copy()

    for i in range(1, len(df)):
        if (df['close'].iloc[i-1] > final_upperband.iloc[i-1]):
            final_upperband.iloc[i] = upperband.iloc[i]
        else:
            final_upperband.iloc[i] = min(upperband.iloc[i], final_upperband.iloc[i-1])

        if (df['close'].iloc[i-1] < final_lowerband.iloc[i-1]):
            final_lowerband.iloc[i] = lowerband.iloc[i]
        else:
            final_lowerband.iloc[i] = max(lowerband.iloc[i], final_lowerband.iloc[i-1])

    # Supertrend direction
    supertrend = pd.Series(index=df.index, dtype='float64')
    in_uptrend = pd.Series(index=df.index, dtype='bool')

    for i in range(len(df)):
        if df['close'].iloc[i] > final_upperband.iloc[i]:
            in_uptrend.iloc[i] = True
        elif df['close'].iloc[i] < final_lowerband.iloc[i]:
            in_uptrend.iloc[i] = False
        else:
            in_uptrend.iloc[i] = in_uptrend.iloc[i-1] if i > 0 else True

        supertrend.iloc[i] = final_lowerband.iloc[i] if in_uptrend.iloc[i] else final_upperband.iloc[i]

    df['supertrend'] = supertrend
    df['in_uptrend'] = in_uptrend
    return df

def calculate_ema(df, period):
    return df["close"].ewm(span=period, adjust=False).mean()

def fetch_ohlcv(symbol, timeframe="15m", limit=100):
    try:
        return exchange.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    except Exception as e:
        print(f"⚠️ Error fetching {symbol}: {e}")
        return None

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
    df = get_supertrend(df)

    signal = None
    if (
        df["EMA9"].iloc[-2] < df["EMA21"].iloc[-2]
        and df["EMA9"].iloc[-1] > df["EMA21"].iloc[-1]
        and df["in_uptrend"].iloc[-1] is True
    ):
        signal = "BUY ✅"
    elif (
        df["EMA9"].iloc[-2] > df["EMA21"].iloc[-2]
        and df["EMA9"].iloc[-1] < df["EMA21"].iloc[-1]
        and df["in_uptrend"].iloc[-1] is False
    ):
        signal = "SELL ❌"
    return signal

# ======================
# Main Runner
# ======================
def run_once():
    print(f"\n===== New Scan at {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S')} UTC =====")
    
    for symbol in symbols_to_check:
        signal = check_signal(symbol)
        if signal:
            print(f"{symbol}: {signal}")
        else:
            print(f"{symbol}: No clear signal")

# ======================
# Entry Point
# ======================
if __name__ == "__main__":
    run_once()
