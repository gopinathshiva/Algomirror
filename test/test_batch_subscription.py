"""
Test batch subscription to multiple instruments
"""

from openalgo import api
import time

# Initialize feed client
client = api(
    api_key="1d323e55e641e70ce3688e67fadddd25f81a2b76410a1333b7273293076f2e49",
    host="http://127.0.0.1:5000",
    ws_url="ws://127.0.0.1:8765"
)

# Batch subscription list - mix of stocks and options
instruments_list = [
    {"exchange": "NSE", "symbol": "TCS"},
    {"exchange": "NSE", "symbol": "INFY"},
    {"exchange": "NSE", "symbol": "RELIANCE"},
    {"exchange": "NFO", "symbol": "NIFTY28AUG2524800CE"},
    {"exchange": "NFO", "symbol": "NIFTY28AUG2524800PE"},
    {"exchange": "NFO", "symbol": "NIFTY28AUG2524850CE"},
    {"exchange": "NFO", "symbol": "NIFTY28AUG2524850PE"}
]

def on_data_received(data):
    symbol = data.get('symbol', 'UNKNOWN')
    ltp = data.get('data', {}).get('ltp', 0)
    print(f"Update: {symbol} = {ltp}")

# Connect and subscribe
print("Connecting...")
client.connect()

print(f"Subscribing to {len(instruments_list)} instruments in batch...")
client.subscribe_quote(instruments_list, on_data_received=on_data_received)

# Wait for data
print("Waiting for market data...")
time.sleep(10)

# Get final quotes
print("\nFinal Quotes:")
quotes = client.get_quotes()
if quotes:
    for key, data in quotes.items():
        if isinstance(data, dict):
            print(f"  {key}: LTP={data.get('ltp', 0)}")

# Cleanup
client.unsubscribe_quote(instruments_list)
client.disconnect()
print("Done!")