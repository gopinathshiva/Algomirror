# AlgoMirror - API Integration Guide

## Overview

AlgoMirror integrates with OpenAlgo's REST API and WebSocket services to provide real-time trading capabilities across multiple broker accounts. This guide covers all integration points, authentication methods, background services, and implementation details.

## OpenAlgo API Integration

### 1. REST API Configuration

#### Base Configuration
```python
# Default OpenAlgo endpoints
OPENALGO_API_HOST = "http://127.0.0.1:5000"
OPENALGO_WS_HOST = "ws://127.0.0.1:8765"

# API Version
API_VERSION = "v1"
```

#### Extended OpenAlgo Client
```python
# app/utils/openalgo_client.py
from openalgo import api

class ExtendedOpenAlgoAPI(api):
    """Extended OpenAlgo client with additional features"""

    def __init__(self, api_key=None, host=None):
        super().__init__(api_key=api_key, host=host)

    def ping(self):
        """Test connection and validate API key"""
        endpoint = f"{self.host}/api/v1/ping"
        headers = {'Content-Type': 'application/json'}
        data = {'apikey': self.api_key}

        response = self.session.post(endpoint, json=data, headers=headers)
        return response.json()
```

### 2. Authentication Methods

#### API Key Authentication
```python
# Encrypted storage and retrieval
class TradingAccount(db.Model):
    api_key_encrypted = db.Column(db.Text)

    def set_api_key(self, api_key):
        """Encrypt and store API key"""
        cipher = Fernet(get_encryption_key())
        self.api_key_encrypted = cipher.encrypt(api_key.encode()).decode()

    def get_api_key(self):
        """Decrypt and return API key"""
        if not self.api_key_encrypted:
            return None
        cipher = Fernet(get_encryption_key())
        return cipher.decrypt(self.api_key_encrypted.encode()).decode()
```

#### Connection Testing
```python
def test_connection(host_url, api_key):
    """Validate OpenAlgo connection"""
    try:
        client = ExtendedOpenAlgoAPI(api_key=api_key, host=host_url)
        response = client.ping()

        if response.get('status') == 'success':
            return {
                'success': True,
                'broker': response.get('broker', 'Unknown'),
                'message': 'Connection successful'
            }
        else:
            return {
                'success': False,
                'message': response.get('message', 'Connection failed')
            }
    except Exception as e:
        return {
            'success': False,
            'message': str(e)
        }
```

## REST API Endpoints

### 1. Account Management APIs

#### Get Funds
```python
def get_funds(account):
    """Retrieve account funds"""
    client = ExtendedOpenAlgoAPI(
        api_key=account.get_api_key(),
        host=account.host_url
    )

    try:
        response = client.funds()
        return {
            'success': True,
            'data': response,
            'cached_at': datetime.now()
        }
    except Exception as e:
        logger.error(f"Failed to get funds: {e}")
        return {'success': False, 'error': str(e)}
```

#### Available Endpoints
```python
# Trading account endpoints
client.funds()           # Get account funds
client.orderbook()       # Get all orders
client.tradebook()       # Get executed trades
client.positionbook()    # Get open positions
client.holdings()        # Get holdings

# Order management endpoints
client.placeorder(data)  # Place new order
client.modifyorder(data) # Modify existing order
client.cancelorder(data) # Cancel order
client.closeposition(data) # Close position

# Market data endpoints
client.quotes(data)      # Get quotes
client.depth(data)       # Get market depth
client.history(data)     # Get historical data
```

### 2. Order Management APIs

#### Place Order
```python
def place_order(account, order_params):
    """Place order through OpenAlgo"""
    client = ExtendedOpenAlgoAPI(
        api_key=account.get_api_key(),
        host=account.host_url
    )

    order_data = {
        'symbol': order_params['symbol'],
        'exchange': order_params['exchange'],
        'action': order_params['action'],  # BUY/SELL
        'quantity': order_params['quantity'],
        'order_type': order_params['order_type'],  # MARKET/LIMIT
        'price': order_params.get('price', 0),
        'product': order_params.get('product', 'MIS'),  # MIS/CNC/NRML
        'trigger_price': order_params.get('trigger_price', 0)
    }

    try:
        response = client.placeorder(order_data)

        # Log order in database
        order = Order(
            account_id=account.id,
            order_id=response.get('order_id'),
            symbol=order_data['symbol'],
            quantity=order_data['quantity'],
            price=order_data['price'],
            status='PENDING'
        )
        db.session.add(order)
        db.session.commit()

        return {'success': True, 'order_id': response.get('order_id')}
    except Exception as e:
        return {'success': False, 'error': str(e)}
```

## WebSocket Integration

### 1. WebSocket Manager Implementation

#### Connection Setup
```python
class ProfessionalWebSocketManager:
    def connect(self, ws_url, api_key):
        """Establish WebSocket connection"""
        self.ws_url = ws_url
        self.api_key = api_key

        # Create WebSocket connection via OpenAlgo client
        self.client = ExtendedOpenAlgoAPI(api_key=api_key, host=self.host)
        self.client.connect()

        # Wait for stabilization
        time.sleep(2)

        # Start in separate thread
        self.ws_thread = threading.Thread(target=self._run_websocket)
        self.ws_thread.daemon = True
        self.ws_thread.start()
```

### 2. Subscription Management

#### Subscribe to Symbols
```python
def subscribe(self, symbol, exchange, mode='ltp'):
    """Subscribe to market data"""
    # Mode mapping
    mode_map = {
        'ltp': 1,      # Last traded price
        'quote': 2,    # Full quote (OHLCV)
        'depth': 3     # Market depth
    }

    self.client.subscribe(symbol, exchange, mode=mode_map.get(mode, 1))
    self.subscriptions.add((symbol, exchange))
```

#### Batch Subscriptions
```python
def subscribe_batch(self, instruments, mode='ltp'):
    """Subscribe to multiple instruments"""
    for instrument in instruments:
        self.subscribe(
            symbol=instrument['symbol'],
            exchange=instrument['exchange'],
            mode=mode
        )
        time.sleep(0.05)  # Prevent overwhelming server
```

### 3. Data Processing

#### Message Handler with Zero-Value Protection
```python
def on_message(self, data):
    """Process incoming WebSocket messages with zero-value protection"""
    symbol = data.get('symbol')
    ltp = data.get('ltp', 0)

    # Zero-value protection: Use cached value if current is zero
    if ltp == 0 and symbol in self.ltp_cache:
        ltp = self.ltp_cache[symbol]
    elif ltp > 0:
        self.ltp_cache[symbol] = ltp

    # Route to appropriate handlers
    if data.get('mode') == 3:  # Depth mode
        self._process_depth_data(data)
    elif data.get('mode') == 2:  # Quote mode
        self._process_quote_data(data)
    else:  # LTP mode
        self._process_ltp_data(data)
```

## Background Services Integration

### 1. Position Monitor Service

#### Purpose
Monitors open positions via WebSocket for real-time P&L calculations. Subscribes ONLY to symbols with open positions (5-50 symbols vs 1000+).

#### Integration
```python
# app/utils/position_monitor.py
class PositionMonitor:
    """Real-time position monitoring via WebSocket"""

    def __init__(self):
        self.subscribed_symbols = set()
        self.price_update_queue = Queue()
        self.flush_interval = 2  # seconds
        self.websocket_manager = None

    def start(self, ws_manager, app):
        """Start position monitoring"""
        self.websocket_manager = ws_manager
        self.app = app

        # Register as quote handler
        ws_manager.register_quote_handler(self._on_quote_update)

        # Start batch flush thread
        self._start_flush_thread()

        # Subscribe to existing open positions
        self._subscribe_open_positions()

    def subscribe_position(self, symbol, execution_id):
        """Subscribe to WebSocket for position monitoring"""
        if symbol not in self.subscribed_symbols:
            self.websocket_manager.subscribe(symbol, 'NFO', mode='quote')
            self.subscribed_symbols.add(symbol)

    def on_order_filled(self, execution_id, symbol):
        """Called by OrderStatusPoller when order fills"""
        self.subscribe_position(symbol, execution_id)

    def on_position_closed(self, symbol, execution_id):
        """Unsubscribe when position is closed"""
        self.websocket_manager.unsubscribe(symbol)
        self.subscribed_symbols.discard(symbol)

    def _on_quote_update(self, data):
        """Handle incoming quote updates"""
        symbol = data.get('symbol')
        if symbol in self.subscribed_symbols:
            self.price_update_queue.put({
                'symbol': symbol,
                'ltp': data.get('ltp'),
                'timestamp': datetime.now()
            })

    def _batch_flush(self):
        """Flush price updates to database every 2 seconds"""
        while self.running:
            time.sleep(self.flush_interval)
            updates = []
            while not self.price_update_queue.empty():
                updates.append(self.price_update_queue.get())

            if updates:
                with self.app.app_context():
                    # Batch database update
                    for update in updates:
                        StrategyExecution.query.filter_by(
                            symbol=update['symbol'],
                            status='entered'
                        ).update({
                            'last_price': update['ltp'],
                            'last_price_updated': update['timestamp']
                        })
                    db.session.commit()
```

### 2. Risk Manager Service

#### Purpose
Enforces risk thresholds (max loss, max profit, trailing stop loss) and triggers automated exits.

#### Integration
```python
# app/utils/risk_manager.py
class RiskManager:
    """Automated risk threshold enforcement"""

    def __init__(self):
        self.position_cache = TTLCache(maxsize=1000, ttl=5)
        self.app = None

    def start(self, app):
        """Initialize risk manager"""
        self.app = app

    def check_risk_for_all_strategies(self):
        """Called every 5 seconds by APScheduler"""
        with self.app.app_context():
            strategies = Strategy.query.filter_by(
                risk_monitoring_enabled=True
            ).all()

            for strategy in strategies:
                if self._has_open_positions(strategy):
                    self.check_risk_for_strategy(strategy)

    def check_risk_for_strategy(self, strategy):
        """Check all risk thresholds for a strategy"""
        current_pnl = self._get_current_pnl(strategy)

        # Max Loss Check
        if strategy.max_loss and strategy.auto_exit_on_max_loss:
            if current_pnl <= -abs(strategy.max_loss):
                if not strategy.max_loss_triggered_at:
                    self._trigger_exit(strategy, 'max_loss', current_pnl)

        # Max Profit Check
        if strategy.max_profit and strategy.auto_exit_on_max_profit:
            if current_pnl >= strategy.max_profit:
                if not strategy.max_profit_triggered_at:
                    self._trigger_exit(strategy, 'max_profit', current_pnl)

        # Trailing Stop Loss (AFL-style)
        if strategy.trailing_sl:
            self._check_trailing_sl(strategy, current_pnl)

    def _check_trailing_sl(self, strategy, current_pnl):
        """AFL-style ratcheting stop loss"""
        if current_pnl > 0:
            if not strategy.trailing_sl_active:
                # Activate TSL when P&L becomes positive
                strategy.trailing_sl_active = True
                strategy.trailing_sl_peak_pnl = current_pnl
                strategy.trailing_sl_initial_stop = -strategy.trailing_sl
                db.session.commit()
            else:
                # Update peak (only moves up)
                if current_pnl > strategy.trailing_sl_peak_pnl:
                    strategy.trailing_sl_peak_pnl = current_pnl
                    db.session.commit()

                # Calculate current stop level
                stop_level = strategy.trailing_sl_initial_stop + strategy.trailing_sl_peak_pnl

                # Check if stop hit
                if current_pnl <= stop_level:
                    self._trigger_exit(strategy, 'trailing_sl', current_pnl)

    def _trigger_exit(self, strategy, event_type, current_pnl):
        """Trigger automated exit and log risk event"""
        # Log risk event
        event = RiskEvent(
            strategy_id=strategy.id,
            event_type=event_type,
            threshold_value=getattr(strategy, event_type.replace('_triggered', ''), 0),
            current_value=current_pnl,
            action_taken='close_all',
            triggered_at=get_ist_now()
        )
        db.session.add(event)

        # Mark strategy
        setattr(strategy, f'{event_type}_triggered_at', get_ist_now())
        setattr(strategy, f'{event_type}_exit_reason', f'{event_type} at {current_pnl}')
        db.session.commit()

        # Close positions with BUY-FIRST priority
        self.close_strategy_positions(strategy, event_type)

    def close_strategy_positions(self, strategy, reason):
        """Close all positions with BUY-FIRST exit priority"""
        executions = StrategyExecution.query.filter_by(
            strategy_id=strategy.id,
            status='entered'
        ).all()

        # Phase 1: Close SELL positions first (place BUY orders)
        sell_positions = [e for e in executions if e.action == 'SELL']
        for execution in sell_positions:
            self._place_exit_order(execution, 'BUY')

        # Phase 2: Close BUY positions (place SELL orders)
        buy_positions = [e for e in executions if e.action == 'BUY']
        for execution in buy_positions:
            self._place_exit_order(execution, 'SELL')

    def _get_current_pnl(self, strategy):
        """Get current P&L from WebSocket > API > Cache"""
        # Try WebSocket prices first
        total_pnl = 0
        for execution in strategy.executions.filter_by(status='entered'):
            if execution.last_price and execution.last_price_updated:
                # Use WebSocket price if recent (< 5 seconds)
                if (datetime.now() - execution.last_price_updated).seconds < 5:
                    pnl = self._calculate_pnl(execution, execution.last_price)
                else:
                    # Fall back to API
                    pnl = self._get_pnl_from_api(execution)
            else:
                pnl = execution.unrealized_pnl or 0
            total_pnl += pnl

        return total_pnl
```

### 3. Order Status Poller Service

#### Purpose
Background polling of pending orders without blocking. Provides callbacks when orders fill.

#### Integration
```python
# app/utils/order_status_poller.py
class OrderStatusPoller:
    """Background order status polling"""

    def __init__(self):
        self.poll_interval = 5  # seconds
        self.running = False
        self.pending_orders = {}  # {order_id: execution_id}
        self.on_fill_callback = None
        self.rate_limiter = {}  # Track last poll per account

    def start(self, app, on_fill_callback=None):
        """Start background polling"""
        self.app = app
        self.on_fill_callback = on_fill_callback
        self.running = True

        # Start polling thread
        self.poll_thread = threading.Thread(target=self._poll_loop, daemon=True)
        self.poll_thread.start()

        # Recover pending orders on restart
        self._recover_pending_orders()

    def add_order(self, order_id, execution_id, account_id):
        """Add order to polling queue"""
        self.pending_orders[order_id] = {
            'execution_id': execution_id,
            'account_id': account_id,
            'added_at': datetime.now()
        }

    def _poll_loop(self):
        """Main polling loop"""
        while self.running:
            try:
                self._update_pending_orders()
                time.sleep(self.poll_interval)
            except Exception as e:
                logger.error(f"Polling error: {e}")

    def _update_pending_orders(self):
        """Update status of pending orders"""
        # Group by account for rate limiting
        orders_by_account = {}
        for order_id, info in list(self.pending_orders.items()):
            account_id = info['account_id']
            if account_id not in orders_by_account:
                orders_by_account[account_id] = []
            orders_by_account[account_id].append((order_id, info))

        # Poll each account (respecting rate limits)
        for account_id, orders in orders_by_account.items():
            # Check rate limit (1 req/sec/account)
            if self._is_rate_limited(account_id):
                continue

            with self.app.app_context():
                account = TradingAccount.query.get(account_id)
                if not account:
                    continue

                try:
                    client = ExtendedOpenAlgoAPI(
                        api_key=account.get_api_key(),
                        host=account.host_url
                    )
                    orderbook = client.orderbook()

                    for order_id, info in orders:
                        self._check_order_status(order_id, info, orderbook)

                    self._update_rate_limit(account_id)

                except Exception as e:
                    logger.error(f"Failed to poll account {account_id}: {e}")

    def _check_order_status(self, order_id, info, orderbook):
        """Check if order has filled"""
        for order in orderbook:
            if order.get('order_id') == order_id:
                if order.get('status') == 'complete':
                    # Order filled
                    execution_id = info['execution_id']

                    # Update execution
                    execution = StrategyExecution.query.get(execution_id)
                    if execution:
                        execution.status = 'entered'
                        execution.entry_price = order.get('average_price')
                        execution.broker_order_status = 'complete'
                        db.session.commit()

                    # Remove from pending
                    del self.pending_orders[order_id]

                    # Callback to Position Monitor
                    if self.on_fill_callback:
                        self.on_fill_callback(execution_id, execution.symbol)

                    logger.info(f"Order {order_id} filled at {order.get('average_price')}")
                break
```

### 4. Session Manager Service

#### Purpose
Manages on-demand option chain sessions with 5-minute auto-expiry.

#### Integration
```python
# app/utils/session_manager.py
class SessionManager:
    """On-demand option chain session management"""

    _instance = None

    @classmethod
    def get_instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.sessions = {}  # {session_id: WebSocketSession}
        self.websocket_manager = None

    def create_session(self, user_id, underlying, expiry):
        """Create new option chain session"""
        session_id = str(uuid.uuid4())

        # Create database record
        session = WebSocketSession(
            user_id=user_id,
            session_id=session_id,
            underlying=underlying,
            expiry=expiry,
            is_active=True,
            last_heartbeat=datetime.now(),
            expires_at=datetime.now() + timedelta(minutes=5)
        )
        db.session.add(session)
        db.session.commit()

        # Subscribe to option chain
        self._subscribe_option_chain(session_id, underlying, expiry)

        return session_id

    def heartbeat(self, session_id):
        """Update session heartbeat (extend expiry)"""
        session = WebSocketSession.query.filter_by(session_id=session_id).first()
        if session:
            session.last_heartbeat = datetime.now()
            session.expires_at = datetime.now() + timedelta(minutes=5)
            db.session.commit()
            return True
        return False

    def cleanup_expired_sessions(self):
        """Called every 1 minute by scheduler"""
        expired = WebSocketSession.query.filter(
            WebSocketSession.expires_at < datetime.now(),
            WebSocketSession.is_active == True
        ).all()

        for session in expired:
            self._unsubscribe_option_chain(session)
            session.is_active = False
            db.session.commit()
            logger.info(f"Cleaned up expired session {session.session_id}")

    def _subscribe_option_chain(self, session_id, underlying, expiry):
        """Subscribe to option chain symbols"""
        symbols = self._generate_option_symbols(underlying, expiry)

        for symbol in symbols:
            self.websocket_manager.subscribe(symbol, 'NFO', mode='depth')

    def _generate_option_symbols(self, underlying, expiry):
        """Generate option symbols for ATM +/- 20 strikes"""
        # Get ATM strike
        atm = self._get_atm_strike(underlying)
        step = 50 if underlying == 'NIFTY' else 100

        symbols = []
        for i in range(-20, 21):
            strike = atm + (i * step)
            symbols.append(f"{underlying}{expiry}{strike}CE")
            symbols.append(f"{underlying}{expiry}{strike}PE")

        return symbols
```

## Internal API Endpoints

### 1. RESTful API Routes

#### Account APIs
```python
@api_bp.route('/accounts', methods=['GET'])
@login_required
@api_rate_limit()
def get_accounts():
    """Get all user accounts"""
    accounts = TradingAccount.query.filter_by(
        user_id=current_user.id
    ).all()

    return jsonify([{
        'id': acc.id,
        'name': acc.account_name,
        'broker': acc.broker,
        'is_primary': acc.is_primary,
        'is_active': acc.is_active
    } for acc in accounts])
```

#### Trading Data APIs
```python
@api_bp.route('/positions/<int:account_id>', methods=['GET'])
@login_required
@api_rate_limit()
def get_positions(account_id):
    """Get positions for account"""
    account = TradingAccount.query.get_or_404(account_id)

    # Verify ownership
    if account.user_id != current_user.id:
        abort(403)

    client = ExtendedOpenAlgoAPI(
        api_key=account.get_api_key(),
        host=account.host_url
    )

    positions = client.positionbook()
    return jsonify(positions)
```

### 2. Strategy Execution APIs

```python
@strategy_bp.route('/execute/<int:strategy_id>', methods=['POST'])
@login_required
def execute_strategy(strategy_id):
    """Execute strategy across selected accounts"""
    strategy = Strategy.query.get_or_404(strategy_id)

    if strategy.user_id != current_user.id:
        abort(403)

    # Get executor instance
    executor = StrategyExecutor(strategy)

    # Execute with parallel order placement
    results = executor.execute_entry()

    # Register with background services
    for result in results:
        if result['success']:
            # Add to order poller
            order_poller.add_order(
                result['order_id'],
                result['execution_id'],
                result['account_id']
            )

    return jsonify({'success': True, 'results': results})
```

## Error Handling

### 1. API Error Codes

```python
ERROR_CODES = {
    'AUTH_FAILED': {'code': 401, 'message': 'Authentication failed'},
    'INVALID_API_KEY': {'code': 403, 'message': 'Invalid API key'},
    'RATE_LIMIT': {'code': 429, 'message': 'Rate limit exceeded'},
    'SERVER_ERROR': {'code': 500, 'message': 'Internal server error'},
    'CONNECTION_ERROR': {'code': 503, 'message': 'Service unavailable'},
    'ACCOUNT_FAILOVER': {'code': 503, 'message': 'Account failover in progress'}
}
```

### 2. Retry Logic with Exponential Backoff

```python
class ExponentialBackoff:
    def __init__(self, base=2, max_delay=60):
        self.base = base
        self.max_delay = max_delay
        self.attempt = 0

    def get_delay(self):
        delay = min(self.base ** self.attempt, self.max_delay)
        self.attempt += 1
        return delay

    def reset(self):
        self.attempt = 0

def retry_with_backoff(func, max_retries=3):
    """Retry API calls with exponential backoff"""
    backoff = ExponentialBackoff()

    for attempt in range(max_retries):
        try:
            result = func()
            backoff.reset()
            return result
        except Exception as e:
            if attempt == max_retries - 1:
                raise

            wait_time = backoff.get_delay()
            logger.warning(f"Retry {attempt + 1}/{max_retries} after {wait_time}s")
            time.sleep(wait_time)
```

## Rate Limiting

### 1. Rate Limit Configuration

```python
# Rate limit tiers
RATE_LIMITS = {
    'global': '1000 per minute',
    'auth': '10 per minute',
    'api': '100 per minute',
    'heavy': '20 per minute'
}

# Order polling rate limit
ORDER_POLL_RATE = '1 per second per account'
```

### 2. Decorator Implementation

```python
from flask_limiter import Limiter

limiter = Limiter(
    app,
    key_func=lambda: get_remote_address(),
    default_limits=["1000 per minute"],
    storage_uri="redis://localhost:6379",  # Production
    strategy="fixed-window"
)

# Custom decorators
def api_rate_limit():
    return limiter.limit("100 per minute")

def heavy_rate_limit():
    return limiter.limit("20 per minute")
```

## Caching Strategy

### 1. Position Cache Implementation

```python
from cachetools import TTLCache

class RiskManager:
    def __init__(self):
        # 5-second TTL cache for position data
        self.position_cache = TTLCache(maxsize=1000, ttl=5)

    def get_positions(self, account_id):
        """Get from cache or fetch from API"""
        cache_key = f'positions_{account_id}'

        if cache_key in self.position_cache:
            return self.position_cache[cache_key]

        # Fetch from API
        positions = self._fetch_positions(account_id)
        self.position_cache[cache_key] = positions
        return positions
```

### 2. Zero-Value Protection Cache

```python
class ProfessionalWebSocketManager:
    def __init__(self):
        self.ltp_cache = {}  # Cache last valid LTP per symbol

    def get_ltp(self, symbol):
        """Get LTP with zero-value protection"""
        current_ltp = self._get_current_ltp(symbol)

        if current_ltp == 0 and symbol in self.ltp_cache:
            # Use cached value if current is zero
            return self.ltp_cache[symbol]
        elif current_ltp > 0:
            # Update cache with valid value
            self.ltp_cache[symbol] = current_ltp
            return current_ltp

        return 0
```

## Monitoring & Logging

### 1. API Call Logging

```python
def log_api_call(endpoint, params, response, duration):
    """Log API calls for monitoring"""
    log_entry = {
        'timestamp': get_ist_now().isoformat(),
        'endpoint': endpoint,
        'params': sanitize_for_logging(params),
        'response_code': response.get('status_code'),
        'duration_ms': duration * 1000,
        'success': response.get('success', False)
    }

    logger.info(json.dumps(log_entry))
```

### 2. Risk Event Logging

```python
def log_risk_event(strategy_id, event_type, threshold, current_value, action):
    """Log risk threshold breach with IST timestamp"""
    event = RiskEvent(
        strategy_id=strategy_id,
        event_type=event_type,
        threshold_value=threshold,
        current_value=current_value,
        action_taken=action,
        triggered_at=get_ist_now()  # IST timezone
    )
    db.session.add(event)
    db.session.commit()

    logger.info(f"Risk event: {event_type} for strategy {strategy_id}, "
                f"threshold={threshold}, current={current_value}, action={action}")
```

## Best Practices

### 1. Security
- Always encrypt API keys at rest
- Use HTTPS for production APIs
- Rate limit all endpoints
- Log all API activity (sanitized)
- Never log decrypted API keys

### 2. Performance
- Use 5-second TTL cache for positions
- Batch database writes (every 2 seconds)
- Use WebSocket for real-time data
- Fall back to API only when WebSocket unavailable
- Respect rate limits (1 req/sec/account for polling)

### 3. Reliability
- Implement retry logic with exponential backoff
- Handle all error cases gracefully
- Maintain connection health checks (every 30 seconds)
- Use failover mechanisms (60-second cooldown)
- Keep audit logs for risk events

### 4. Exit Priority
- Always use BUY-FIRST exit priority
- Close SELL positions before BUY positions
- Retry failed exits (max 3 attempts)
- Track exit orders via OrderStatusPoller

This comprehensive API integration guide provides all the necessary information to integrate AlgoMirror with OpenAlgo and implement robust trading functionality with real-time monitoring and automated risk management.
