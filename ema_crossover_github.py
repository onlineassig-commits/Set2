"""
rt.py — Pump→Dump Screener (GitHub + Telegram)
----------------------------------------------
- Runs a single scan (no infinite loop)
- Scans your meme coin list across multiple exchanges
- Detects pump + confirm
- Prints ranked coin names to logs
- Sends ranked coin names to Telegram

Dependencies:
  pip install ccxt pandas numpy tqdm requests
"""

import ccxt
import pandas as pd
import numpy as np
from datetime import timedelta
from tqdm import tqdm
import warnings
import os
import requests

warnings.filterwarnings("ignore")

# ---------------- TELEGRAM CONFIG ----------------
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")   # store in GitHub Secrets
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def send_telegram_message(text: str):
    """Send message to Telegram bot"""
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram not configured. Skipping send.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": text}
    try:
        r = requests.post(url, data=data, timeout=10)
        if r.status_code != 200:
            print("Telegram send failed:", r.text)
    except Exception as e:
        print("Telegram error:", e)

# ---------------- USER CONFIG ----------------
COIN_LIST = [
    'DOGE/USDT','SHIB/USDT','PEPE/USDT','WIF/USDT','BONK/USDT','FLOKI/USDT','MEME/USDT',
    'KOMA/USDT','DOGS/USDT','NEIROETH/USDT','1000RATS/USDT','ORDI/USDT','PIPPIN/USDT',
    'BAN/USDT','1000SHIB/USDT','OM/USDT','CHILLGUY/USDT','PONKE/USDT','BOME/USDT',
    'MYRO/USDT','PEOPLE/USDT','PENGU/USDT','SPX/USDT','1000BONK/USDT','PNUT/USDT',
    'FARTCOIN/USDT','HIPPO/USDT','AIXBT/USDT','BRETT/USDT','VINE/USDT','MOODENG/USDT',
    'MUBARAK/USDT','MEW/USDT','POPCAT/USDT','1000FLOKI/USDT','1000CAT/USDT','ACT/USDT',
    'SLERF/USDT','DEGEN/USDT','1000PEPE/USDT'
]

EXCHANGE_LIST = ['binance', 'bybit', 'okx', 'kucoin']

ROLL_1H = 100
ROLL_15M = 200
WATCH_HOURS = 3

# thresholds
Z_RET_THRESHOLD = 1.8
Z_VOL_THRESHOLD = 2.0
VOL_MULT_15 = 3.0
BETA_CLOSE_NEAR_LOW = 0.30

EMA_FAST = 21
EMA_SLOW = 50

# ---------------- HELPERS ----------------
def get_exchange(exchange_id):
    try:
        ex_class = getattr(ccxt, exchange_id)
        return ex_class({'enableRateLimit': True})
    except Exception:
        return None

def fetch_ohlcv_fallback(symbol: str, timeframe: str, limit: int = 500):
    for ex_id in EXCHANGE_LIST:
        ex = get_exchange(ex_id)
        if ex is None: continue
        try:
            ex.load_markets()
            if not getattr(ex, 'has', {}).get('fetchOHLCV', True):
                continue
            ohl = ex.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
            if not ohl: continue
            df = pd.DataFrame(ohl, columns=['ts', 'open','high','low','close','volume'])
            df['datetime'] = pd.to_datetime(df['ts'], unit='ms', utc=True)
            return df.dropna().sort_values('datetime').reset_index(drop=True), ex_id
        except Exception:
            continue
    return None, None

def add_emas(df):
    if df is None or df.empty: return df
    df = df.copy()
    df['EMA_21'] = df['close'].ewm(span=EMA_FAST, adjust=False).mean()
    df['EMA_50'] = df['close'].ewm(span=EMA_SLOW, adjust=False).mean()
    return df

# ---------------- DETECTION ----------------
def compute_1h_stats(df_1h):
    df = df_1h.copy()
    df['ret_pct'] = df['close'].pct_change() * 100
    df['ret_mean'] = df['ret_pct'].rolling(ROLL_1H, min_periods=20).mean()
    df['ret_std'] = df['ret_pct'].rolling(ROLL_1H, min_periods=20).std().replace(0, np.nan)
    df['z_ret'] = (df['ret_pct'] - df['ret_mean']) / df['ret_std']
    df['vol_mean_1h'] = df['volume'].rolling(ROLL_1H, min_periods=20).mean()
    df['vol_std_1h'] = df['volume'].rolling(ROLL_1H, min_periods=20).std().replace(0, np.nan)
    df['z_vol'] = (df['volume'] - df['vol_mean_1h']) / df['vol_std_1h']
    return df

def compute_15m_stats(df_15m):
    df = df_15m.copy()
    df['vol_mean_15m'] = df['volume'].rolling(ROLL_15M, min_periods=20).mean()
    return df

def detect_pumps_1h(df_1h_stats):
    mask = (df_1h_stats['z_ret'] >= Z_RET_THRESHOLD) & (df_1h_stats['z_vol'] >= Z_VOL_THRESHOLD)
    return df_1h_stats.index[mask].tolist()

def is_15m_bearish_vol_spike(bar_15m):
    rng = bar_15m['high'] - bar_15m['low']
    if rng <= 0: return False
    close_near_low = bar_15m['close'] <= bar_15m['low'] + BETA_CLOSE_NEAR_LOW * rng
    bearish = bar_15m['close'] < bar_15m['open']
    mean15 = bar_15m.get('vol_mean_15m', np.nan)
    if pd.isna(mean15) or mean15 == 0: return False
    vol_spike = bar_15m['volume'] >= VOL_MULT_15 * mean15
    return bearish and close_near_low and vol_spike

# ---------------- SCORING ----------------
def compute_signal_score(pump_row, confirm_row):
    zret = float(pump_row.get('z_ret', 0.0))
    zvol = float(pump_row.get('z_vol', 0.0))
    s1 = min(1.0, zret / 5.0)
    s2 = min(1.0, zvol / 6.0)
    vol_ratio = confirm_row['volume'] / max(confirm_row.get('vol_mean_15m', 1.0), 1.0)
    s3 = min(1.0, vol_ratio / (VOL_MULT_15 * 2))
    dt = (confirm_row['datetime'] - pump_row['datetime']).total_seconds() / 60.0
    s4 = max(0.0, 1.0 - (dt / (WATCH_HOURS * 60.0)))
    return float(0.35*s1 + 0.30*s2 + 0.25*s3 + 0.10*s4)

# ---------------- MAIN ----------------
def scan_once():
    signals = []
    for coin in tqdm(COIN_LIST, desc="Scanning coins", unit="coin"):
        df_1h, ex1 = fetch_ohlcv_fallback(coin, '1h', limit=ROLL_1H+50)
        if df_1h is None or len(df_1h) < ROLL_1H: continue
        df_15m, ex15 = fetch_ohlcv_fallback(coin, '15m', limit=ROLL_15M+50)
        if df_15m is None or len(df_15m) < 40: continue
        df_1h_stats = add_emas(compute_1h_stats(df_1h))
        df_15m_stats = add_emas(compute_15m_stats(df_15m))
        pump_idx_list = detect_pumps_1h(df_1h_stats)
        pump_idx_list = [i for i in pump_idx_list if i >= len(df_1h_stats)-24]
        for pidx in pump_idx_list:
            pump_row = df_1h_stats.iloc[pidx]
            pump_time = pump_row['datetime']
            watch_end = pump_time + timedelta(hours=WATCH_HOURS)
            win15 = df_15m_stats[(df_15m_stats['datetime'] > pump_time) & (df_15m_stats['datetime'] <= watch_end)]
            if win15.empty: continue
            confirmed = None
            for _, bar in win15.iterrows():
                if is_15m_bearish_vol_spike(bar):
                    confirmed = bar; break
            if confirmed is not None:
                score = compute_signal_score(pump_row, confirmed)
                signals.append({
                    'ticker': coin,
                    'score': score
                })
    signals.sort(key=lambda x: x['score'], reverse=True)
    return signals

if __name__ == "__main__":
    results = scan_once()
    if not results:
        msg = "No signals"
    else:
        msg = "\n".join(s['ticker'] for s in results)

    print(msg)
    send_telegram_message(msg)
