import ccxt
import pandas as pd
import time
from datetime import datetime

# 바이낸스 객체 생성
exchange = ccxt.binance({
    'enableRateLimit': True,
})

timeframeBong = '4h'  # 4시간 봉

# 심볼 필터링: USDT 마켓만
def get_usdt_pairs():
    markets = exchange.load_markets()
    return [symbol for symbol in markets if symbol.endswith('/USDT') and not symbol.startswith('BTC')]

# 과거 캔들 데이터 가져오기
def fetch_ohlcv(symbol, limit=180):
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe=timeframeBong, limit=limit)
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df.set_index('timestamp')['close']
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

# 메인 실행 함수
def find_highly_correlated_coins(base_symbol='BTC/USDT', top_n=10):
    base_data = fetch_ohlcv(base_symbol)
    if base_data is None:
        print("Failed to fetch BTC data.")
        return

    usdt_pairs = get_usdt_pairs()
    correlations = {}

    for symbol in usdt_pairs:
        time.sleep(exchange.rateLimit / 1000)  # 요청 제한
        close_prices = fetch_ohlcv(symbol)
        if close_prices is not None and len(close_prices) == len(base_data):
            corr = base_data.corr(close_prices)
            if pd.notna(corr):
                correlations[symbol] = corr

    # 상관계수 내림차순 정렬
    sorted_corr = sorted(correlations.items(), key=lambda x: x[1], reverse=True)
    print(f"\nTop {top_n} coins correlated with {base_symbol} ({timeframeBong}):\n")
    for symbol, corr in sorted_corr[:top_n]:
        print(f"{symbol}: {corr:.4f}")

# 실행
find_highly_correlated_coins()

# 코인 전체 개수
print(f"\nTotal number of coins: {len(get_usdt_pairs())}")