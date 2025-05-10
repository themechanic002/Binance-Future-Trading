import ccxt
import pandas as pd
import numpy as np
import time
from dotenv import load_dotenv
import os

load_dotenv()

# ◾️ 바이낸스 API 키 설정 (본인의 키로 교체하세요)
api_key = os.getenv('BINANCE_API_KEY')
secret = os.getenv('BINANCE_SECRET_KEY')

# ◾️ 사용할 잔고 비율 (예: 20%)
ORDER_RATIO = 0.9

# ◾️ 상관계수 기준
corr_threshold = 0.8

# ◾️ 레버리지 설정
leverage = 5

# ◾️ Binance 선물 객체 생성
binance = ccxt.binance({
    'apiKey': api_key,
    'secret': secret,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future'  # 선물 마켓 사용
    }
})

# =========================================================
# 🧩 함수 정의
# =========================================================

def get_usdt_pairs():
    """🔍 USDT 마켓 선물 심볼 리스트 반환"""
    binance.options['defaultType'] = 'future'
    markets = binance.load_markets()
    return [
        symbols for symbols, data in markets.items()
        if data.get('quote') == 'USDT'
        and data.get('contract')  # 선물 계약인지 확인
        and data.get('linear')    # USDT-M 선물인지 확인
        and data.get('expiry') is None  # 만기일이 없는 심볼만
        and not symbols.startswith('BTC')
    ]

def fetch_ohlcv(symbol, timeframe='4h', limit=70):
    """📈 OHLCV 데이터 가져오기 (4시간봉 기준)"""
    try:
        return binance.fetch_ohlcv(symbol, timeframe=timeframe, limit=limit)
    except Exception as e:
        print(f"[에러] {symbol} 데이터 가져오기 실패: {e}")
        return None

def get_correlated_coins(base_symbol='BTC/USDT', top_n=10, corr_threshold=0.8):
    """📈 BTC와의 상관계수를 기준으로 상위 코인 탐색"""
    base_ohlcv = fetch_ohlcv(base_symbol)
    if base_ohlcv is None:
        print("❌ Failed to fetch BTC data.")
        return {}

    base_close = pd.Series([x[4] for x in base_ohlcv]).dropna()
    usdt_pairs = get_usdt_pairs()
    correlations = {}
    checked = 0

    for symbol in usdt_pairs:
        if symbol == base_symbol:
            continue

        time.sleep(binance.rateLimit / 1000)  # API rate limit
        ohlcv = fetch_ohlcv(symbol)
        if ohlcv is None:
            continue

        close = pd.Series([x[4] for x in ohlcv]).dropna()
        if len(close) != len(base_close):
            continue

        if close.std() == 0 or base_close.std() == 0:
            continue  # 변동성 없음

        corr = base_close.corr(close)
        if pd.notna(corr):
            correlations[symbol] = corr
            checked += 1

    print(f"🔍 총 {checked}개 코인과 상관계수 계산 완료.")

    # 정렬: 양의 상관관계 우선
    sorted_corr = sorted(correlations.items(), key=lambda x: x[1], reverse=True)

    # 상위 N개 출력
    print(f"\n📊 [상관계수 상위 {top_n} 코인]")
    for i, (symbol, corr) in enumerate(sorted_corr[:top_n], 1):
        print(f"{i:2}. {symbol:15} | 상관계수: {corr:.4f}")

    # 필터링: 일정 threshold 이상만 선택
    filtered = {symbol: round(corr, 4) for symbol, corr in sorted_corr if corr >= corr_threshold}

    return dict(list(filtered.items())[:top_n])


def get_balance():
    """💰 USDT 선물 잔고 조회"""
    balance = binance.fetch_balance({'type': 'future'})
    return balance['total']['USDT']

def get_position_mode():
    """⚙️ 포지션 모드(Hedge / One-Way) 조회"""
    try:
        mode_info = binance.fapiPrivateGetPositionSideDual()
        return True if mode_info['dualSidePosition'] else False
    except Exception as e:
        return f'포지션 모드 조회 실패: {e}'

def place_orders(symbols_corr_dict, total_usdt, leverage, is_hedge_mode):
    """📌 매수 주문 실행"""
    per_coin_usdt = total_usdt / len(symbols_corr_dict)
    print("-------------------------------")
    print(f"💰 매수할 코인 개수: {len(symbols_corr_dict)}개")
    print(f"💰 각 코인 {len(symbols_corr_dict)}개에 할당된 금액: {per_coin_usdt} USDT")
    print(f"💰 총 투자 금액(전체 잔고의 {ORDER_RATIO*100}%): {total_usdt} USDT")
    print("-------------------------------")
    bought_symbols = []

    for symbol, corr in symbols_corr_dict.items():
        try:
            orderbook = binance.fetch_order_book(symbol, limit=5)
            best_ask = orderbook['asks'][0][0]  # 매도 1호가
            print(f"\n💡 {symbol} 매도 1호가: {best_ask} USDT")

            # 매수 수량 계산
            amount = round((per_coin_usdt * leverage) / best_ask, 5)

            print(f"🛒 {symbol} 매수 주문 시도 중 (가격: {best_ask}, 수량: {amount})")

            # 레버리지 설정
            binance.set_leverage(leverage, symbol)

            # 매도1호가로 주문 실행
            if is_hedge_mode:
                # Hedge Mode: positionSide 명시 필수
                order = binance.create_order(
                    symbol=symbol,
                    type='limit',
                    side='buy',
                    amount=amount,
                    price=best_ask,
                    params={
                        'positionSide': 'LONG'
                    }
                )
            else:
                # One-Way Mode: 지정가 매수
                order = binance.create_order(
                    symbol=symbol,
                    type='limit',
                    side='buy',
                    amount=amount,
                    price=best_ask,
                    params={
                        'timeInForce': 'GTC'
                    }
                )
            print(f"✅ 주문 완료: {order['id']}")
            bought_symbols.append(symbol)


        except ccxt.InsufficientFunds as e:
            print(f"❌ 잔고 부족: {symbol} - {e}")
        except ccxt.InvalidOrder as e:
            print(f"⚠️ 주문 오류 (포지션 모드 문제일 수 있음): {symbol} - {e}")
        except Exception as e:
            print(f"❓ 기타 오류: {symbol} - {e}")

    # ✅ 주문된 코인들 출력
    if bought_symbols:
        print("\n📦 매수 완료된 코인:")
        for sym in bought_symbols:
            print(f"  - {sym}")
    else:
        print("\n🚫 매수된 코인이 없습니다.")

# =========================================================
# 🚀 메인 실행
# =========================================================

def main():
    
    is_hedge_mode = get_position_mode()  # 기본값: 단방향 모드

    try:
        print(f"🔧 현재 Hedge 포지션 모드 여부: {get_position_mode()}")

        # 🔍 상관계수 기반 코인 선택
        symbols_corr_dict = get_correlated_coins('BTC/USDT', 10, corr_threshold)
        if not symbols_corr_dict:
            print("\n🚫 상관계수 0.9 이상인 코인이 없습니다.")
            return

        # 💰 잔고 조회
        balance = get_balance()
        print(f"\n💰 USDT 잔고: {balance:.2f} USDT")

        # 🛒 주문 실행
        order_amount = balance * ORDER_RATIO
        place_orders(symbols_corr_dict, order_amount, leverage, is_hedge_mode)

    except Exception as e:
        print(f"\n❗️예상치 못한 에러 발생: {e}")

# =========================================================
# ▶️ 실행
# =========================================================
if __name__ == "__main__":
    main()
