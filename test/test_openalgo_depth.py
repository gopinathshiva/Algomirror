"""
OpenAlgo WebSocket Market Depth Example
"""

from openalgo import api
import time

# Initialize feed client with explicit parameters
client = api(
    api_key="1d323e55e641e70ce3688e67fadddd25f81a2b76410a1333b7273293076f2e49",  # Test API key
    host="http://127.0.0.1:5000",  # Replace with your API host
    ws_url="ws://127.0.0.1:8765"  # Explicit WebSocket URL (can be different from REST API host)
)

# Test instruments
instruments_list = [
    {"exchange": "NSE", "symbol": "TCS"},
    {"exchange": "NFO", "symbol": "NIFTY28AUG2524800CE"}  # Test with option
]

def on_data_received(data):
    print("Market Depth Update:")
    print(f"  Symbol: {data.get('symbol')}")
    print(f"  LTP: {data.get('ltp')}")
    bids = data.get('bids', [])
    asks = data.get('asks', [])
    if bids:
        print(f"  Best Bid: {bids[0]}")
    if asks:
        print(f"  Best Ask: {asks[0]}")

# Connect and subscribe
client.connect()
client.subscribe_depth(instruments_list, on_data_received=on_data_received)

# Poll Market Depth data a few times
for i in range(10):  # Reduced to 10 for testing
    print(f"\nPoll {i+1}:")
    depth = client.get_depth()
    if depth:
        for symbol, data in depth.items():
            print(f"  {symbol}: LTP={data.get('ltp', 0)}, Bid={data.get('bid', 0)}, Ask={data.get('ask', 0)}")
    time.sleep(0.5)

# Cleanup
client.unsubscribe_depth(instruments_list)
client.disconnect()