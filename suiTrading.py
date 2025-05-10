import ccxt
from dotenv import load_dotenv
import os

load_dotenv()

# ◾️ 바이낸스 API 키 설정 (본인의 키로 교체하세요)
api_key = os.getenv('BINANCE_API_KEY')
api_secret = os.getenv('BINANCE_SECRET_KEY')


# 바이낸스 선물 객체 설정
binance = ccxt.binance({
    'apiKey': api_key,
    'secret': api_secret,
    'enableRateLimit': True,
    'options': {
        'defaultType': 'future'  # 선물 거래
    }
})

symbol = 'SUI/USDT'
leverage = 2

try:
    binance.load_markets()
    binance.set_leverage(leverage, symbol)

    # 현재 SUI 가격 출력
    ticker = binance.fetch_ticker(symbol)
    price = ticker['last']
    print(f"📈 현재 {symbol} 가격: {price:.4f} USDT")


    # 잔고 확인
    balance = binance.fetch_balance()
    usdt_balance = balance['total']['USDT']
    print(f"💼 현재 사용 가능한 USDT 잔고: {usdt_balance:.2f} USDT")


    # 현재 포지션 모드 조회 (Hedge mode면 True, One-Way mode면 False)
    position_mode_info = binance.fapiPrivateGetPositionSideDual()
    is_hedge_mode = position_mode_info['dualSidePosition']
    print(f"⚙️ 현재 포지션 모드: {'Hedge Mode (양방향)' if is_hedge_mode else 'One-Way Mode (단방향)'}")

    # ================================================================

    # 사용자 입력 받기
    usdt_amount = float(input("💰 매수할 금액을 USDT 단위로 입력하세요: "))


    if usdt_balance < usdt_amount:
        print("❌ 주문 실패: USDT 잔고가 부족합니다.")
        exit()


    # 현재 호가창 조회 (depth 5)
    orderbook = binance.fetch_order_book(symbol, limit=5)
    best_ask = orderbook['asks'][0][0]  # 매도 1호가
    print(f"💡 매도 1호가 (지정가 기준): {best_ask:.4f} USDT")


    # 매수 수량 계산
    amount = usdt_amount / best_ask

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

    # 주문 결과 출력
    print("✅ 주문 완료!")
    print(f"🆔 주문 ID: {order['id']}")
    print(f"📦 주문 수량: {order['amount']} SUI")
    print(f"💵 체결 평균가: {order['average'] or 'N/A'} USDT")
    print(f"📊 상태: {order['status']}")

except ccxt.InsufficientFunds:
    print("❌ 예외 발생: 잔고가 부족합니다.")
except ValueError:
    print("⚠️ 숫자 형식으로 입력해주세요.")
except ccxt.BaseError as e:
    print(f"❌ 바이낸스 API 오류: {str(e)}")
except Exception as e:
    print(f"❌ 기타 오류 발생: {str(e)}")
