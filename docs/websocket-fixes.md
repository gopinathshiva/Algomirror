# WebSocket and Option Chain Fixes

## Issues Fixed

### 1. Symbol Format Issue (FIXED)
**Problem**: Option symbols were being generated incorrectly with format like `NIFTY28AUG2523800CE` (year in strike)
**Solution**: Corrected to proper format `NIFTY28AUG2524800CE` (expiry + strike + type)

### 2. WebSocket Authentication (FIXED)
**Problem**: Was using Bearer token in headers
**Solution**: Using message-based authentication with `{"action": "authenticate", "api_key": "..."}`

### 3. WebSocket Data Flow (DEBUGGING)
**Problem**: WebSocket server returns error "At least one symbol must be specified"
**Current Status**: 
- Authentication successful
- Symbols format correct (verified via REST API)
- WebSocket server not accepting subscription messages

## Symbol Format Specification

Correct OpenAlgo format for options:
- Pattern: `[BASE][DDMMMYY][STRIKE][CE/PE]`
- Example: `NIFTY28AUG2524800CE`
  - BASE: NIFTY
  - Date: 28AUG25 (28 August 2025)
  - Strike: 24800
  - Type: CE (Call European)

## WebSocket Protocol

### Authentication Flow
```json
// Send after connection
{
    "action": "authenticate",
    "api_key": "your_api_key"
}

// Response
{
    "type": "auth",
    "status": "success"
}
```

### Subscription Format
```json
{
    "action": "subscribe",
    "mode": "depth",  // or "quote" or "ltp"
    "instruments": [
        {
            "exchange": "NFO",
            "symbol": "NIFTY28AUG2524800CE"
        }
    ]
}
```

## Testing Steps

1. **Verify Symbol Format**:
   ```python
   # Test with REST API
   client.quotes(symbol='NIFTY28AUG2524800CE', exchange='NFO')
   ```

2. **Check WebSocket Connection**:
   - Authentication should succeed
   - Subscriptions should be sent with correct format

## Next Steps

The WebSocket server appears to have different requirements than documented. Possible issues:
1. WebSocket server might expect different subscription format
2. Symbols might need to be validated against a symbol master first
3. Server might require batch subscriptions differently

## Logs to Check

Enable detailed logging with these markers:
- `[WS_MSG]` - All incoming WebSocket messages
- `[WS_SUBSCRIBE]` - Subscription attempts
- `[WS_DATA]` - Market data received
- `[OPTION_CHAIN]` - Option chain updates