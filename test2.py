import ccxt
import pandas as pd
import time
from tqdm import tqdm

# 바이낸스 선물 연결
binance = ccxt.binance({
    'options': {'defaultType': 'future'}
})

# 4시간봉 데이터 개수
limit = 100  # 약 16일치

# 기준 심볼
base_symbol = 'BTC/USDT'

# 1. BTC/USDT의 4시간봉 종가 데이터 가져오기
def fetch_ohlcv(symbol):
    try:
        ohlcv = binance.fetch_ohlcv(symbol, timeframe='4h', limit=limit)
        df = pd.DataFrame(ohlcv, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

btc_df = fetch_ohlcv(base_symbol)
if btc_df is None:
    raise Exception("BTC/USDT 데이터를 가져오는 데 실패했습니다.")

btc_close = btc_df['close'].reset_index(drop=True)

# 2. 바이낸스 선물 시장의 모든 심볼 가져오기
markets = binance.load_markets()
symbols = [s for s in markets if '/USDT' in s and markets[s]['contract'] and markets[s]['active']]
symbols.remove(base_symbol)

# 3. 각 심볼의 4시간봉 종가를 가져와 BTC/USDT와의 상관계수 계산
correlations = []

for symbol in tqdm(symbols, desc="Fetching and comparing"):
    df = fetch_ohlcv(symbol)
    if df is not None and len(df) == len(btc_close):
        close_prices = df['close'].reset_index(drop=True)
        corr = close_prices.corr(btc_close)
        if not pd.isna(corr):
            correlations.append((symbol, corr))
    time.sleep(0.2)  # 속도 제한 (Rate Limit 대응)

# 4. 상관계수 기준 상위 10개 코인 출력
top_10 = sorted(correlations, key=lambda x: abs(x[1]), reverse=True)[:10]

print("\nBTC/USDT와 상관계수 기준 상위 10개 코인:")
for symbol, corr in top_10:
    print(f"{symbol}: 상관계수 = {corr:.4f}")
