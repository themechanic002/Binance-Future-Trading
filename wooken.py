import ccxt
import pandas as pd
import time
import math
import numpy as np
from pprint import pprint
from dotenv import load_dotenv
import os

load_dotenv()

# ================================
# 1) API 키 설정
# ================================
BINANCE_API_KEY = os.getenv('BINANCE_API_KEY')
BINANCE_SECRET_KEY = os.getenv('BINANCE_SECRET_KEY')

# ================================
# 2) 바이낸스 객체 생성 (선물 시장)
# ================================
exchange = ccxt.binance({
    'apiKey': BINANCE_API_KEY,
    'secret': BINANCE_SECRET_KEY,
    'enableRateLimit': True,
})
timeframeBong = '4h'  # 4시간 봉

# ================================
# 3) USDT 마켓 페어만 필터링
# ================================
def get_usdt_pairs():
    markets = exchange.load_markets()
    return [
        symbol for symbol, data in markets.items()
        if data.get('quote') == 'USDT'
        and data.get('contract')  # 선물 계약인지 확인
        and data.get('linear')    # USDT-M 선물인지 확인
        and not symbol.startswith('BTC')
    ]


# ================================
# 4) 과거 캔들 데이터(종가) 조회
# ================================
def fetch_ohlcv(symbol, limit=180):
    try:
        data = exchange.fetch_ohlcv(symbol, timeframe=timeframeBong, limit=limit)
        df = pd.DataFrame(data, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        df['timestamp'] = pd.to_datetime(df['timestamp'], unit='ms')
        return df.set_index('timestamp')['close']
    except Exception as e:
        print(f"Error fetching {symbol}: {e}")
        return None

# ================================
# 5) BTC/USDT 대비 상관계수 상위 N개 찾기
# ================================
def find_highly_correlated_coins(base_symbol='BTC/USDT', top_n=10):
    base_data = fetch_ohlcv(base_symbol)
    if base_data is None:
        print("Failed to fetch BTC data.")
        return []

    usdt_pairs = get_usdt_pairs()
    correlations = {}

    for symbol in usdt_pairs:
        time.sleep(exchange.rateLimit / 1000)
        close = fetch_ohlcv(symbol)
        if close is not None and len(close) == len(base_data):
            # NaN 값 제거
            base_data_clean = base_data.dropna()
            close_clean = close.dropna()

            if len(base_data_clean) == 0 or len(close_clean) == 0:
                continue  # 데이터가 없으면 넘어감

            # 표준편차가 0이면 상관계수 계산을 건너뜀
            stddev_base = np.std(base_data_clean)
            stddev_close = np.std(close_clean)

            if stddev_base == 0 or stddev_close == 0:
                continue  # 표준편차가 0이면 상관계수 계산을 건너뜀

            corr = base_data_clean.corr(close_clean)
            if pd.notna(corr):
                correlations[symbol] = corr

    sorted_corr = sorted(correlations.items(), key=lambda x: x[1], reverse=True)
    return sorted_corr[:top_n]

# ================================
# 6) 상관계수 높은 종목 시장가 매수
# ================================
def buy_top_correlated_coins(top_symbols, balance, leverage=2, min_order_value=20):
    # —— 실제 가용 잔고(free) 기준 사용 ——
    usdt_balance = balance['free']['USDT']
    use_ratio    = 0.7  # 사용할 비율
    base_invest  = usdt_balance * use_ratio
    portion_base = base_invest / len(top_symbols)

    print(f"💰 가용 USDT 잔고(free): {usdt_balance:.2f}")
    print(f"📌 레버리지 미적용 투자금: {base_invest:.2f} USDT")
    print(f"📌 종목별 기본 배분금: {portion_base:.2f} USDT")

    # 포지션 모드(헷지/단방향) 확인
    pos_info      = exchange.fapiPrivateGetPositionSideDual()
    is_hedge_mode = pos_info.get('dualSidePosition', False)
    print(f"⚙️ 포지션 모드: {'Hedge Mode' if is_hedge_mode else 'One-Way Mode'}")

    for symbol in top_symbols:
        try:
            # 1) 심볼별 레버리지 설정 (통합 메소드)
            exchange.set_leverage(leverage, symbol)

            # 2) 가격 조회 및 수량 계산
            price         = exchange.fetch_ticker(symbol)['last']
            position_size = portion_base * leverage
            raw_amount    = position_size / price
            amount        = math.floor(raw_amount * 1_000) / 1_000  # 소수점 셋째자리 버림
            required_margin = position_size / leverage  # = portion_base

            # 최소 거래 금액(Notional) 체크
            if amount * price < min_order_value:
                print(f"⚠️ {symbol} → 최소 Notional({min_order_value} USDT) 미만, 건너뜁니다.")
                continue

            print(f"→ {symbol} 주문 전 점검: 현재가={price}, 수량={amount}, "
                  f"포지션규모={position_size:.2f}, 증거금={required_margin:.2f}")

            # 3) 시장가 매수
            params = {'positionSide': 'LONG'} if is_hedge_mode else {}
            order = exchange.create_market_buy_order(symbol, amount, params=params)
            pprint(order)
            print(f"✅ {symbol} 매수 완료 | 증거금 소요: {required_margin:.2f} USDT")

        except Exception as e:
            print(f"❌ {symbol} 주문 실패: {e}")

        time.sleep(0.2)

# ================================
# 7) 메인 실행부
# ================================
def main():
    top_n = 2
    threshold = 0.9

    # 상관계수 상위 top_n 조회 → threshold 이상 필터
    top = find_highly_correlated_coins(base_symbol='BTC/USDT', top_n=top_n)
    symbols = [sym for sym, corr in top if corr >= threshold]
    print(f"📈 상관계수 ≥ {threshold} 종목: {symbols}")

    if not symbols:
        print("❌ 해당 조건을 만족하는 종목이 없습니다.")
        return

    balance = exchange.fetch_balance(params={"type": "future"})
    buy_top_correlated_coins(symbols, balance)

if __name__ == "__main__":
    main()
