"""
OpenAlgo WebSocket Quote Feed Example
"""

from openalgo import api
import time

# Initialize feed client with explicit parameters
client = api(
    api_key="1d323e55e641e70ce3688e67fadddd25f81a2b76410a1333b7273293076f2e49",  # Test API key
    host="http://127.0.0.1:5000",  # Replace with your API host
    ws_url="ws://127.0.0.1:8765"  # Explicit WebSocket URL (can be different from REST API host)
)

# MCX instruments for testing
instruments_list = [
    {"exchange": "NSE_INDEX", "symbol": "NIFTY"},
    {"exchange": "NSE", "symbol": "INFY"},
    {"exchange": "NSE", "symbol": "TCS"}
]

def on_data_received(data):
    print("Quote Update:")
    print(data)

# Connect and subscribe
client.connect()
client.subscribe_quote(instruments_list, on_data_received=on_data_received)

# Poll Quote data a few times
for i in range(10):  # Reduced to 10 for testing
    print(f"\nPoll {i+1}:")
    quotes = client.get_quotes()
    if quotes:
        for symbol, data in quotes.items():
            print(f"  {symbol}: LTP={data.get('ltp', 0)}")
    time.sleep(0.5)

# Cleanup
client.unsubscribe_quote(instruments_list)
client.disconnect()