"""
Test WebSocket data flow from connection to option chain updates
"""

import json
import time
import logging
from datetime import datetime
from app.utils.websocket_manager import ProfessionalWebSocketManager
from app.utils.option_chain import OptionChainManager
from openalgo import api

# Configure detailed logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

logger = logging.getLogger(__name__)

def test_websocket_flow():
    """Test complete WebSocket data flow"""
    
    print("\n" + "="*60)
    print("WEBSOCKET DATA FLOW TEST")
    print("="*60)
    
    # Test parameters - update these with your actual values
    API_KEY = "your_api_key_here"  # Replace with actual API key
    WS_URL = "ws://127.0.0.1:8765"
    API_HOST = "http://127.0.0.1:5000"
    
    try:
        # Step 1: Create WebSocket manager
        print("\n[1] Creating WebSocket manager...")
        ws_manager = ProfessionalWebSocketManager()
        
        # Step 2: Connect to WebSocket
        print("[2] Connecting to WebSocket...")
        connected = ws_manager.connect(WS_URL, API_KEY)
        
        if not connected:
            print("   FAILED: Could not connect to WebSocket")
            return
        
        print("   SUCCESS: WebSocket connected")
        
        # Wait for authentication
        print("[3] Waiting for authentication...")
        time.sleep(2)
        
        if not ws_manager.authenticated:
            print("   FAILED: Authentication failed")
            print("   Check your API key and WebSocket server")
            return
        
        print("   SUCCESS: Authenticated")
        
        # Step 4: Create API client
        print("[4] Creating API client...")
        api_client = api(api_key=API_KEY, host=API_HOST)
        
        # Step 5: Get expiry
        print("[5] Getting NIFTY expiry...")
        expiry_response = api_client.expiry(
            symbol='NIFTY',
            exchange='NFO',
            instrumenttype='options'
        )
        
        if expiry_response.get('status') != 'success':
            print(f"   FAILED: Could not get expiry: {expiry_response}")
            return
        
        expiries = expiry_response.get('data', [])
        if not expiries:
            print("   FAILED: No expiries available")
            return
        
        expiry = expiries[0]
        print(f"   SUCCESS: Using expiry {expiry}")
        
        # Step 6: Create option chain manager
        print("[6] Creating option chain manager...")
        option_manager = OptionChainManager(
            underlying='NIFTY',
            expiry=expiry,
            websocket_manager=ws_manager
        )
        
        # Step 7: Initialize option chain
        print("[7] Initializing option chain...")
        option_manager.initialize(api_client)
        option_manager.start_monitoring()
        print(f"   ATM Strike: {option_manager.atm_strike}")
        print(f"   Total strikes: {len(option_manager.option_data)}")
        
        # Step 8: Check WebSocket status
        print("\n[8] WebSocket Status:")
        ws_status = ws_manager.get_status()
        print(f"   Connected: {ws_status.get('connected')}")
        print(f"   Subscriptions: {ws_status.get('subscriptions')}")
        print(f"   Messages received: {ws_status.get('metrics', {}).get('messages_received', 0)}")
        
        # Step 9: Wait for data and check updates
        print("\n[9] Waiting for market data (10 seconds)...")
        print("   Watch the logs for incoming messages...")
        
        for i in range(10):
            time.sleep(1)
            
            # Check if we're receiving data
            metrics = ws_manager.connection_pool.get('metrics', {}) if ws_manager.connection_pool else {}
            msg_count = metrics.get('messages_received', 0)
            
            # Get a sample option data
            sample_data = None
            for strike_data in option_manager.option_data.values():
                if strike_data['tag'] == 'ATM':
                    sample_data = strike_data
                    break
            
            if sample_data:
                ce_ltp = sample_data['ce_data'].get('ltp', 0)
                pe_ltp = sample_data['pe_data'].get('ltp', 0)
                print(f"   [{i+1}s] Messages: {msg_count}, ATM CE: {ce_ltp}, ATM PE: {pe_ltp}")
        
        # Step 10: Final status
        print("\n[10] Final Status:")
        option_chain_data = option_manager.get_option_chain()
        
        # Count non-zero values
        non_zero_ce = sum(1 for opt in option_chain_data['options'] if opt['ce_data']['ltp'] > 0)
        non_zero_pe = sum(1 for opt in option_chain_data['options'] if opt['pe_data']['ltp'] > 0)
        
        print(f"   Underlying LTP: {option_chain_data['underlying_ltp']}")
        print(f"   CE with data: {non_zero_ce}/{len(option_chain_data['options'])}")
        print(f"   PE with data: {non_zero_pe}/{len(option_chain_data['options'])}")
        
        if non_zero_ce == 0 and non_zero_pe == 0:
            print("\n   WARNING: No price data received!")
            print("   Possible issues:")
            print("   1. Market might be closed")
            print("   2. WebSocket server might not be sending data")
            print("   3. Symbol format might be incorrect")
            print("   4. Check WebSocket server logs for errors")
        else:
            print("\n   SUCCESS: Receiving market data!")
        
    except Exception as e:
        print(f"\nERROR: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        try:
            if 'ws_manager' in locals():
                ws_manager.disconnect()
                print("\nWebSocket disconnected")
        except:
            pass

if __name__ == "__main__":
    print("\n" + "*"*60)
    print("IMPORTANT: Update API_KEY, WS_URL, and API_HOST before running!")
    print("*"*60)
    
    test_websocket_flow()