import time
import ccxt

print("Coin Auto Trading Application Started")
print("=" * 50)

# 간단한 테스트
try:
    print("Testing CCXT library...")
    exchange = ccxt.binance()
    print(f"Exchange: {exchange.name}")
    print("CCXT library loaded successfully!")
except Exception as e:
    print(f"Error: {e}")

# 컨테이너 유지를 위한 루프
print("\nApplication running. Press Ctrl+C to stop.")
while True:
    time.sleep(60)
