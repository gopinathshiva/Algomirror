# AlgoMirror - Features Implementation Guide

## Feature Overview

This guide provides detailed implementation instructions for all major features in AlgoMirror, including multi-account management, WebSocket integration, option chain monitoring, trading operations, and the new real-time monitoring infrastructure.

## New Architecture Highlights (2024)

- **Position Monitor**: WebSocket-based real-time position tracking for open positions only
- **Risk Manager**: Automated 5-second risk checks with AFL-style trailing stop-loss
- **Order Status Poller**: Background order tracking with fill notifications
- **Session Manager**: On-demand option chain sessions with 5-minute auto-expiry
- **Supertrend Exit Service**: Technical indicator-based exit monitoring
- **BUY-FIRST Exit Priority**: Closes SELL positions before BUY during risk exits
- **Zero-Value Protection**: Caches last valid LTP to prevent false risk triggers
- **Batch Database Writes**: Position Monitor flushes every 2 seconds

## 1. Multi-Account Management

### Account Model Implementation

```python
# app/models.py
class TradingAccount(db.Model):
    __tablename__ = 'trading_accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    account_name = db.Column(db.String(100), nullable=False)
    broker = db.Column(db.String(50), nullable=False)
    api_key_encrypted = db.Column(db.Text)
    host_url = db.Column(db.String(200), default='http://127.0.0.1:5000')
    websocket_url = db.Column(db.String(200), default='ws://127.0.0.1:8765')
    is_primary = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    user = db.relationship('User', backref='trading_accounts')
    
    def set_as_primary(self):
        """Set this account as primary, unset others"""
        TradingAccount.query.filter_by(
            user_id=self.user_id
        ).update({'is_primary': False})
        
        self.is_primary = True
        db.session.commit()
        
        # Trigger option chain startup
        from app.utils.option_chain import start_option_chains
        start_option_chains(self)
```

### Account Management Routes

```python
# app/accounts/routes.py
@accounts_bp.route('/add', methods=['GET', 'POST'])
@login_required
def add_account():
    form = AccountForm()
    
    if form.validate_on_submit():
        # Test connection before saving
        test_result = test_connection(
            form.host_url.data,
            form.api_key.data
        )
        
        if test_result['success']:
            account = TradingAccount(
                user_id=current_user.id,
                account_name=form.account_name.data,
                broker=test_result.get('broker', 'Unknown'),
                host_url=form.host_url.data,
                websocket_url=form.websocket_url.data
            )
            account.set_api_key(form.api_key.data)
            
            # Set as primary if first account
            if current_user.trading_accounts.count() == 0:
                account.is_primary = True
            
            db.session.add(account)
            db.session.commit()
            
            flash(f'Account {account.account_name} added successfully')
            return redirect(url_for('accounts.list'))
        else:
            flash(f'Connection failed: {test_result["message"]}')
    
    return render_template('accounts/add.html', form=form)
```

### Account Switching

```python
@accounts_bp.route('/switch/<int:account_id>', methods=['POST'])
@login_required
def switch_primary(account_id):
    account = TradingAccount.query.get_or_404(account_id)
    
    if account.user_id != current_user.id:
        abort(403)
    
    account.set_as_primary()
    
    # Update WebSocket connections
    websocket_manager.switch_account(account)
    
    flash(f'Switched to {account.account_name}')
    return redirect(url_for('main.dashboard'))
```

## 2. WebSocket Real-Time Data

### WebSocket Manager Implementation

```python
# app/utils/websocket_manager.py
class ProfessionalWebSocketManager:
    def __init__(self):
        self.connection_pool = {}
        self.data_processor = WebSocketDataProcessor()
        self.subscriptions = set()
        self.active = False
        
    def initialize_for_account(self, account, backup_accounts=None):
        """Initialize WebSocket for account with failover"""
        self.create_connection_pool(account, backup_accounts)
        
        # Connect to primary account
        success = self.connect(
            account.websocket_url,
            account.get_api_key()
        )
        
        if success:
            logger.info(f"WebSocket connected for {account.account_name}")
            return True
        else:
            logger.error(f"Failed to connect WebSocket for {account.account_name}")
            return False
    
    def subscribe_option_chain(self, underlying, expiry, strikes):
        """Subscribe to option chain symbols"""
        instruments = []
        
        for strike in strikes:
            # Call option
            instruments.append({
                'symbol': f"{underlying}{expiry}{strike}CE",
                'exchange': 'NFO'
            })
            
            # Put option
            instruments.append({
                'symbol': f"{underlying}{expiry}{strike}PE",
                'exchange': 'NFO'
            })
        
        # Subscribe with depth mode for market depth
        self.subscribe_batch(instruments, mode='depth')
```

### WebSocket Data Processing

```python
class WebSocketDataProcessor:
    def __init__(self):
        self.handlers = {
            'quote': [],
            'depth': [],
            'ltp': []
        }
        
    def process_market_data(self, data):
        """Route data to appropriate handlers"""
        mode = data.get('mode', 'ltp')
        
        for handler in self.handlers.get(mode, []):
            try:
                handler(data)
            except Exception as e:
                logger.error(f"Handler error: {e}")
```

### Real-Time UI Updates

```javascript
// app/static/js/websocket_client.js
class WebSocketClient {
    constructor(accountId) {
        this.accountId = accountId;
        this.eventSource = null;
        this.reconnectAttempts = 0;
    }
    
    connect() {
        // Use Server-Sent Events for real-time updates
        this.eventSource = new EventSource(`/api/stream/${this.accountId}`);
        
        this.eventSource.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleUpdate(data);
        };
        
        this.eventSource.onerror = () => {
            this.handleError();
        };
    }
    
    handleUpdate(data) {
        // Update UI based on data type
        if (data.type === 'position') {
            this.updatePosition(data);
        } else if (data.type === 'option_chain') {
            this.updateOptionChain(data);
        }
    }
    
    updatePosition(data) {
        const row = document.querySelector(`[data-symbol="${data.symbol}"]`);
        if (row) {
            row.querySelector('.ltp').textContent = data.ltp.toFixed(2);
            row.querySelector('.pnl').textContent = data.pnl.toFixed(2);
            
            // Color code P&L
            const pnlCell = row.querySelector('.pnl');
            pnlCell.className = data.pnl >= 0 ? 'text-success' : 'text-danger';
        }
    }
}
```

## 3. Option Chain Monitoring

### Option Chain Manager

```python
# app/utils/option_chain.py
class OptionChainManager:
    def __init__(self, underlying, expiry):
        self.underlying = underlying
        self.expiry = expiry
        self.strike_step = 50 if underlying == 'NIFTY' else 100
        self.option_data = {}
        self.monitoring_active = False
        
    def start_monitoring(self):
        """Start background monitoring"""
        if self.monitoring_active:
            return
        
        self.monitoring_active = True
        
        # Calculate strikes
        self.calculate_strikes()
        
        # Subscribe via WebSocket
        self.subscribe_to_websocket()
        
        # Start monitoring thread
        self.monitor_thread = threading.Thread(target=self.monitor_loop)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
    
    def calculate_strikes(self):
        """Calculate strike range around ATM"""
        # Get underlying LTP
        ltp = self.get_underlying_ltp()
        
        # Calculate ATM
        self.atm_strike = round(ltp / self.strike_step) * self.strike_step
        
        # Generate strike range (ATM ± 20 strikes)
        self.strikes = []
        for i in range(-20, 21):
            strike = self.atm_strike + (i * self.strike_step)
            self.strikes.append({
                'strike': strike,
                'tag': self.get_strike_tag(i)
            })
    
    def get_strike_tag(self, offset):
        """Generate strike tag (ITM20...ATM...OTM20)"""
        if offset == 0:
            return 'ATM'
        elif offset < 0:
            return f'ITM{abs(offset)}'
        else:
            return f'OTM{offset}'
    
    def process_depth_update(self, data):
        """Process market depth update"""
        symbol = data['symbol']
        
        # Parse symbol to get strike and type
        strike_info = self.parse_option_symbol(symbol)
        
        if strike_info:
            # Update option data with depth
            self.option_data[symbol] = {
                'strike': strike_info['strike'],
                'type': strike_info['type'],
                'ltp': data.get('ltp', 0),
                'bid': data.get('bids', [{}])[0].get('price', 0),
                'ask': data.get('asks', [{}])[0].get('price', 0),
                'bid_qty': data.get('bids', [{}])[0].get('quantity', 0),
                'ask_qty': data.get('asks', [{}])[0].get('quantity', 0),
                'volume': data.get('volume', 0),
                'oi': data.get('oi', 0),
                'updated_at': datetime.now()
            }
```

### Option Chain Display

```html
<!-- app/templates/trading/option_chain.html -->
<div class="option-chain-container">
    <div class="controls">
        <select id="underlying">
            <option value="NIFTY">NIFTY</option>
            <option value="BANKNIFTY">BANKNIFTY</option>
        </select>
        
        <select id="expiry">
            {% for expiry in expiries %}
            <option value="{{ expiry }}">{{ expiry }}</option>
            {% endfor %}
        </select>
    </div>
    
    <table class="option-chain-table">
        <thead>
            <tr>
                <th colspan="8">CALL</th>
                <th>Strike</th>
                <th>Tag</th>
                <th colspan="8">PUT</th>
            </tr>
            <tr>
                <!-- Call headers -->
                <th>OI</th>
                <th>Vol</th>
                <th>Bid Q</th>
                <th>Bid</th>
                <th>LTP</th>
                <th>Ask</th>
                <th>Ask Q</th>
                <th>Spread</th>
                <!-- Strike -->
                <th></th>
                <th></th>
                <!-- Put headers -->
                <th>Spread</th>
                <th>Ask Q</th>
                <th>Ask</th>
                <th>LTP</th>
                <th>Bid</th>
                <th>Bid Q</th>
                <th>Vol</th>
                <th>OI</th>
            </tr>
        </thead>
        <tbody id="option-chain-data">
            <!-- Dynamic rows -->
        </tbody>
    </table>
</div>
```

## 4. Real-Time Monitoring Infrastructure (NEW)

### Background Service Orchestration

```python
# app/utils/background_service.py
class BackgroundService:
    """Orchestrate all background monitoring services"""

    def __init__(self, app):
        self._app = app
        self._position_monitor = None
        self._risk_manager = None
        self._order_poller = None
        self._session_manager = None
        self._running = False
        self._lock = threading.Lock()

    def start_services(self):
        """Start all background services (called once at app startup)"""
        with self._lock:
            if self._running:
                return

            with self._app.app_context():
                # Initialize shared WebSocket
                self._init_websocket()

                # Start Position Monitor
                self._position_monitor = PositionMonitor(self._websocket)
                self._position_monitor.start()

                # Start Risk Manager (runs every 5 seconds)
                self._risk_manager = RiskManager()
                self._scheduler.add_job(
                    self._risk_manager.check_all_executions,
                    'interval',
                    seconds=5,
                    id='risk_manager'
                )

                # Start Order Status Poller
                self._order_poller = OrderStatusPoller()
                self._order_poller.start()

                # Start Session Manager
                self._session_manager = SessionManager()

            self._running = True
            logger.info("Background services started successfully")
```

### Position Monitor Implementation

```python
# app/utils/position_monitor.py
class PositionMonitor:
    """
    Real-time position tracking using WebSocket.
    Subscribes ONLY to symbols with open positions (5-50 vs 1000+ option chain).
    """

    BATCH_FLUSH_INTERVAL = 2  # Flush to database every 2 seconds

    def __init__(self, websocket_manager):
        self._ws = websocket_manager
        self._subscribed_symbols = set()
        self._price_cache = {}  # Zero-value protection
        self._update_queue = queue.Queue()
        self._running = False

    def start(self):
        """Start position monitoring"""
        self._running = True
        self._subscribe_to_open_positions()

        # Start batch writer thread
        self._writer_thread = threading.Thread(target=self._batch_writer)
        self._writer_thread.daemon = True
        self._writer_thread.start()

    def _subscribe_to_open_positions(self):
        """Subscribe to WebSocket for symbols with open positions"""
        # Get all active executions with open positions
        executions = StrategyExecution.query.filter(
            StrategyExecution.status == 'active',
            StrategyExecution.total_quantity != 0
        ).all()

        symbols = set()
        for execution in executions:
            for leg in execution.legs:
                if leg.quantity != 0:
                    symbols.add(leg.symbol)

        # Subscribe via WebSocket
        for symbol in symbols:
            if symbol not in self._subscribed_symbols:
                self._ws.subscribe(symbol, mode='ltp')
                self._subscribed_symbols.add(symbol)

        logger.info(f"Position Monitor: Subscribed to {len(symbols)} symbols")

    def on_price_update(self, symbol, ltp):
        """Handle WebSocket price update with zero-value protection"""
        # Zero-value protection: ignore zero prices
        if ltp <= 0:
            cached = self._price_cache.get(symbol)
            if cached:
                ltp = cached
            else:
                return  # No valid price available

        # Cache valid price
        self._price_cache[symbol] = ltp

        # Queue for batch update
        self._update_queue.put({
            'symbol': symbol,
            'ltp': ltp,
            'timestamp': datetime.now()
        })

    def _batch_writer(self):
        """Flush price updates to database in batches"""
        while self._running:
            time.sleep(self.BATCH_FLUSH_INTERVAL)

            updates = []
            while not self._update_queue.empty():
                try:
                    updates.append(self._update_queue.get_nowait())
                except queue.Empty:
                    break

            if updates:
                self._flush_to_database(updates)

    def _flush_to_database(self, updates):
        """Batch write position updates"""
        try:
            with self._app.app_context():
                # Group updates by symbol (latest only)
                latest = {}
                for update in updates:
                    latest[update['symbol']] = update

                # Update positions
                for symbol, data in latest.items():
                    Position.query.filter_by(symbol=symbol).update({
                        'ltp': data['ltp'],
                        'updated_at': data['timestamp']
                    })

                db.session.commit()
                logger.debug(f"Flushed {len(latest)} position updates")
        except Exception as e:
            logger.error(f"Batch write failed: {e}")
            db.session.rollback()
```

### Risk Manager Implementation

```python
# app/utils/risk_manager.py
class RiskManager:
    """
    Automated risk enforcement running every 5 seconds.
    Supports: max loss, max profit, AFL-style trailing stop-loss, Supertrend exits.
    """

    CHECK_INTERVAL = 5  # seconds
    EXIT_RETRY_LIMIT = 3

    def __init__(self):
        self._ist = timezone('Asia/Kolkata')

    def check_all_executions(self):
        """Check risk thresholds for all active executions"""
        executions = StrategyExecution.query.filter(
            StrategyExecution.status == 'active',
            StrategyExecution.risk_monitoring_enabled == True
        ).all()

        for execution in executions:
            try:
                self._check_execution_risk(execution)
            except Exception as e:
                logger.error(f"Risk check failed for execution {execution.id}: {e}")

    def _check_execution_risk(self, execution):
        """Check all risk thresholds for an execution"""
        current_pnl = self._calculate_current_pnl(execution)

        # Check max loss (if configured)
        if execution.max_loss_amount and current_pnl <= -execution.max_loss_amount:
            self._trigger_exit(execution, 'max_loss', current_pnl, -execution.max_loss_amount)
            return

        # Check max profit (if configured)
        if execution.max_profit_amount and current_pnl >= execution.max_profit_amount:
            self._trigger_exit(execution, 'max_profit', current_pnl, execution.max_profit_amount)
            return

        # Check AFL-style trailing stop loss
        if execution.trailing_sl_amount:
            self._check_trailing_stop(execution, current_pnl)

    def _check_trailing_stop(self, execution, current_pnl):
        """
        AFL-style trailing stop-loss:
        - Activates when P&L becomes positive
        - Tracks peak P&L achieved
        - Stop level = Initial Stop + Peak P&L
        - Exits when current_pnl <= trailing_stop_level
        """
        initial_stop = -execution.trailing_sl_amount

        # Update peak P&L if current is higher
        if current_pnl > (execution.peak_pnl or 0):
            execution.peak_pnl = current_pnl
            db.session.commit()

        # Calculate trailing stop level
        peak = execution.peak_pnl or 0
        if peak > 0:
            # Trailing stop moves up as profit grows
            trailing_stop_level = initial_stop + peak
        else:
            # Not yet in profit, use initial stop
            trailing_stop_level = initial_stop

        # Check if stop triggered
        if current_pnl <= trailing_stop_level:
            self._trigger_exit(
                execution, 'trailing_stop',
                current_pnl, trailing_stop_level
            )

    def _trigger_exit(self, execution, event_type, current_value, threshold):
        """Execute exit with BUY-FIRST priority"""
        logger.warning(
            f"Risk triggered: {event_type} for execution {execution.id}, "
            f"current={current_value}, threshold={threshold}"
        )

        # Log risk event with IST timestamp
        self._log_risk_event(execution, event_type, current_value, threshold, 'exit_initiated')

        # Exit with BUY-FIRST priority (close SELL positions first)
        try:
            self._execute_exit_orders(execution)
            execution.status = 'exited'
            execution.exit_reason = event_type
            execution.exit_time = datetime.now(self._ist)
            db.session.commit()

            self._log_risk_event(execution, event_type, current_value, threshold, 'exit_completed')
        except Exception as e:
            logger.error(f"Exit failed: {e}")
            execution.exit_retry_count = (execution.exit_retry_count or 0) + 1
            db.session.commit()

            self._log_risk_event(execution, event_type, current_value, threshold, 'exit_failed',
                               details={'error': str(e)})

    def _execute_exit_orders(self, execution):
        """
        BUY-FIRST exit priority:
        Close SELL positions before BUY positions to avoid margin issues.
        """
        legs = execution.legs

        # Separate by position type
        sell_legs = [l for l in legs if l.action == 'SELL' and l.quantity != 0]
        buy_legs = [l for l in legs if l.action == 'BUY' and l.quantity != 0]

        # Exit SELL positions first (they have margin locked)
        for leg in sell_legs:
            self._close_leg(execution, leg)

        # Then exit BUY positions
        for leg in buy_legs:
            self._close_leg(execution, leg)

    def _log_risk_event(self, execution, event_type, trigger_value, threshold, action, details=None):
        """Log risk event with IST timestamp"""
        event = RiskEvent(
            strategy_execution_id=execution.id,
            event_type=event_type,
            trigger_value=trigger_value,
            threshold_value=threshold,
            action_taken=action,
            details=json.dumps(details) if details else None,
            created_at=datetime.now(self._ist)
        )
        db.session.add(event)
        db.session.commit()
```

### Order Status Poller Implementation

```python
# app/utils/order_status_poller.py
class OrderStatusPoller:
    """
    Background polling of pending orders.
    Rate-limit aware: 1 request/sec/account, parallel across accounts.
    """

    POLL_INTERVAL = 5  # seconds
    MAX_WORKERS = 10

    def __init__(self):
        self._running = False
        self._executor = ThreadPoolExecutor(max_workers=self.MAX_WORKERS)
        self._callbacks = []

    def start(self):
        """Start order status polling"""
        self._running = True
        self._poll_thread = threading.Thread(target=self._poll_loop)
        self._poll_thread.daemon = True
        self._poll_thread.start()

    def register_callback(self, callback):
        """Register callback for order fill notifications"""
        self._callbacks.append(callback)

    def _poll_loop(self):
        """Main polling loop"""
        while self._running:
            try:
                self._poll_pending_orders()
            except Exception as e:
                logger.error(f"Order poll error: {e}")

            time.sleep(self.POLL_INTERVAL)

    def _poll_pending_orders(self):
        """Poll orders in parallel by account"""
        # Get pending orders grouped by account
        pending = Order.query.filter(
            Order.status.in_(['PENDING', 'OPEN', 'TRIGGER_PENDING'])
        ).all()

        # Group by account
        by_account = {}
        for order in pending:
            account_id = order.account_id
            if account_id not in by_account:
                by_account[account_id] = []
            by_account[account_id].append(order)

        # Poll each account in parallel
        futures = []
        for account_id, orders in by_account.items():
            future = self._executor.submit(self._poll_account_orders, account_id, orders)
            futures.append(future)

        # Wait for all to complete
        for future in futures:
            try:
                future.result(timeout=30)
            except Exception as e:
                logger.error(f"Account poll failed: {e}")

    def _poll_account_orders(self, account_id, orders):
        """Poll orders for a single account (rate-limited)"""
        account = TradingAccount.query.get(account_id)
        if not account:
            return

        client = ExtendedOpenAlgoAPI(
            api_key=account.get_api_key(),
            host=account.host_url
        )

        # Get order book (single API call for all orders)
        order_book = client.orderbook()

        # Update order statuses
        for order in orders:
            matching = next(
                (o for o in order_book if o.get('orderid') == order.order_id),
                None
            )

            if matching:
                old_status = order.status
                new_status = matching.get('status', 'UNKNOWN')

                if old_status != new_status:
                    order.status = new_status
                    order.filled_quantity = matching.get('filledqty', 0)
                    order.average_price = matching.get('avgprice', 0)

                    # Notify callbacks on fill
                    if new_status == 'COMPLETE':
                        for callback in self._callbacks:
                            try:
                                callback(order)
                            except Exception as e:
                                logger.error(f"Callback error: {e}")

        db.session.commit()
```

### Session Manager Implementation

```python
# app/utils/session_manager.py
class SessionManager:
    """
    Manage on-demand option chain sessions.
    Sessions auto-expire after 5 minutes of inactivity.
    """

    SESSION_EXPIRY_MINUTES = 5

    def __init__(self):
        self._active_sessions = {}

    def create_session(self, user_id, account_id, instrument):
        """Create option chain session (on-demand, not at market open)"""
        session_key = f"{user_id}_{instrument}"

        # Check if session exists
        if session_key in self._active_sessions:
            session = self._active_sessions[session_key]
            session['last_heartbeat'] = datetime.utcnow()
            return session['session_id']

        # Create new session
        session_id = secrets.token_urlsafe(32)
        session = WebSocketSession(
            session_id=session_id,
            user_id=user_id,
            account_id=account_id,
            instrument=instrument,
            session_type='option_chain',
            is_active=True,
            last_heartbeat=datetime.utcnow(),
            expires_at=datetime.utcnow() + timedelta(minutes=self.SESSION_EXPIRY_MINUTES)
        )

        db.session.add(session)
        db.session.commit()

        self._active_sessions[session_key] = {
            'session_id': session_id,
            'last_heartbeat': datetime.utcnow()
        }

        logger.info(f"Option chain session created for {instrument}")
        return session_id

    def heartbeat(self, session_id):
        """Extend session expiry on heartbeat"""
        session = WebSocketSession.query.filter_by(
            session_id=session_id,
            is_active=True
        ).first()

        if session:
            session.last_heartbeat = datetime.utcnow()
            session.expires_at = datetime.utcnow() + timedelta(minutes=self.SESSION_EXPIRY_MINUTES)
            db.session.commit()
            return True

        return False

    def cleanup_expired(self):
        """Close expired sessions (called periodically)"""
        expired = WebSocketSession.query.filter(
            WebSocketSession.is_active == True,
            WebSocketSession.expires_at < datetime.utcnow()
        ).all()

        for session in expired:
            session.is_active = False
            logger.info(f"Session expired: {session.session_id[:8]}... ({session.instrument})")

            # Remove from active sessions cache
            session_key = f"{session.user_id}_{session.instrument}"
            self._active_sessions.pop(session_key, None)

        db.session.commit()
        return len(expired)
```

## 5. Trading Operations

### Order Management

```python
# app/trading/routes.py
@trading_bp.route('/place_order', methods=['POST'])
@login_required
def place_order():
    data = request.json
    account = get_primary_account()
    
    # Validate order parameters
    order_params = {
        'symbol': data['symbol'],
        'exchange': data['exchange'],
        'action': data['action'],  # BUY/SELL
        'quantity': int(data['quantity']),
        'order_type': data['order_type'],  # MARKET/LIMIT
        'price': float(data.get('price', 0)),
        'product': data.get('product', 'MIS')
    }
    
    # Place order via OpenAlgo
    client = ExtendedOpenAlgoAPI(
        api_key=account.get_api_key(),
        host=account.host_url
    )
    
    try:
        response = client.placeorder(order_params)
        
        if response.get('status') == 'success':
            # Store order in database
            order = Order(
                account_id=account.id,
                order_id=response['order_id'],
                symbol=order_params['symbol'],
                quantity=order_params['quantity'],
                price=order_params['price'],
                order_type=order_params['order_type'],
                status='PENDING'
            )
            db.session.add(order)
            db.session.commit()
            
            return jsonify({
                'success': True,
                'order_id': response['order_id']
            })
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 400
```

### Position Management

```python
@trading_bp.route('/positions')
@login_required
def positions():
    account = get_primary_account()
    
    if not account:
        flash('No primary account configured')
        return redirect(url_for('accounts.add'))
    
    try:
        client = ExtendedOpenAlgoAPI(
            api_key=account.get_api_key(),
            host=account.host_url
        )
        
        positions = client.positionbook()
        
        # Calculate additional metrics
        for position in positions:
            position['pnl'] = calculate_pnl(position)
            position['pnl_percent'] = calculate_pnl_percent(position)
        
        return render_template(
            'trading/positions.html',
            positions=positions,
            account=account
        )
    except Exception as e:
        flash(f'Error fetching positions: {e}')
        return redirect(url_for('main.dashboard'))
```

### Smart Order Execution

```python
class SmartOrderExecutor:
    def __init__(self, option_chain_manager):
        self.option_chain = option_chain_manager
        
    def place_smart_order(self, symbol, action, quantity):
        """Place order with optimal pricing"""
        # Get market depth
        depth = self.option_chain.get_option_depth(symbol)
        
        if not depth:
            raise ValueError(f"No market data for {symbol}")
        
        # Determine execution price
        if action == 'BUY':
            # Place slightly above ask for quick execution
            execution_price = depth['ask'] * 1.001
        else:  # SELL
            # Place slightly below bid
            execution_price = depth['bid'] * 0.999
        
        # Check spread
        spread_percent = ((depth['ask'] - depth['bid']) / depth['ltp']) * 100
        
        if spread_percent > 2:  # Wide spread
            # Use limit order at mid price
            execution_price = (depth['ask'] + depth['bid']) / 2
            order_type = 'LIMIT'
        else:
            order_type = 'LIMIT'
        
        return {
            'symbol': symbol,
            'action': action,
            'quantity': quantity,
            'order_type': order_type,
            'price': round(execution_price, 2)
        }
```

## 5. Dashboard Implementation

### Main Dashboard

```python
# app/main/routes.py
@main_bp.route('/dashboard')
@login_required
def dashboard():
    # Get user's accounts
    accounts = current_user.trading_accounts.filter_by(
        is_active=True
    ).all()
    
    primary_account = next(
        (acc for acc in accounts if acc.is_primary), 
        None
    )
    
    # Aggregate data
    dashboard_data = {
        'total_accounts': len(accounts),
        'primary_account': primary_account,
        'total_positions': 0,
        'total_pnl': 0,
        'websocket_status': 'disconnected'
    }
    
    if primary_account:
        try:
            # Get account data
            client = ExtendedOpenAlgoAPI(
                api_key=primary_account.get_api_key(),
                host=primary_account.host_url
            )
            
            # Funds
            funds = client.funds()
            dashboard_data['available_balance'] = funds.get('available_balance', 0)
            
            # Positions
            positions = client.positionbook()
            dashboard_data['total_positions'] = len(positions)
            dashboard_data['total_pnl'] = sum(
                p.get('pnl', 0) for p in positions
            )
            
            # WebSocket status
            dashboard_data['websocket_status'] = websocket_manager.get_status()
            
        except Exception as e:
            logger.error(f"Dashboard data error: {e}")
    
    return render_template(
        'main/dashboard.html',
        **dashboard_data
    )
```

### Dashboard UI

```html
<!-- app/templates/main/dashboard.html -->
{% extends "layout.html" %}

{% block content %}
<div class="dashboard">
    <!-- Account Summary -->
    <div class="stats-grid">
        <div class="stat-card">
            <h3>Active Accounts</h3>
            <div class="stat-value">{{ total_accounts }}</div>
        </div>
        
        <div class="stat-card">
            <h3>Available Balance</h3>
            <div class="stat-value">₹{{ available_balance|format_number }}</div>
        </div>
        
        <div class="stat-card">
            <h3>Open Positions</h3>
            <div class="stat-value">{{ total_positions }}</div>
        </div>
        
        <div class="stat-card">
            <h3>Total P&L</h3>
            <div class="stat-value {{ 'text-success' if total_pnl >= 0 else 'text-danger' }}">
                ₹{{ total_pnl|format_number }}
            </div>
        </div>
    </div>
    
    <!-- WebSocket Status -->
    <div class="connection-status">
        <span class="status-indicator {{ 'active' if websocket_status == 'connected' else 'inactive' }}"></span>
        WebSocket: {{ websocket_status }}
    </div>
    
    <!-- Quick Actions -->
    <div class="quick-actions">
        <a href="{{ url_for('trading.positions') }}" class="btn btn-primary">View Positions</a>
        <a href="{{ url_for('trading.option_chain') }}" class="btn btn-secondary">Option Chain</a>
        <a href="{{ url_for('accounts.list') }}" class="btn btn-outline">Manage Accounts</a>
    </div>
</div>
{% endblock %}
```

## 6. Failover Implementation

### Account Failover Logic

```python
class FailoverController:
    def __init__(self):
        self.primary_account = None
        self.backup_accounts = []
        self.failover_history = []
        
    def setup_failover_chain(self, user_id):
        """Setup failover hierarchy"""
        accounts = TradingAccount.query.filter_by(
            user_id=user_id,
            is_active=True
        ).order_by(
            TradingAccount.is_primary.desc()
        ).all()
        
        if accounts:
            self.primary_account = accounts[0]
            self.backup_accounts = accounts[1:]
    
    def handle_connection_failure(self):
        """Handle primary account failure"""
        if not self.backup_accounts:
            logger.error("No backup accounts available")
            return False
        
        # Get next backup
        next_account = self.backup_accounts.pop(0)
        
        # Record failover
        self.failover_history.append({
            'from': self.primary_account.account_name,
            'to': next_account.account_name,
            'timestamp': datetime.now(),
            'reason': 'connection_failure'
        })
        
        # Switch to backup
        self.primary_account = next_account
        
        # Reconnect WebSocket
        return websocket_manager.switch_account(next_account)
```

## 7. Activity Logging

### Comprehensive Logging

```python
# app/utils/logging.py
def log_user_activity(action, details=None):
    """Log user activity for audit"""
    activity = ActivityLog(
        user_id=current_user.id if current_user.is_authenticated else None,
        action=action,
        details=details,
        ip_address=request.remote_addr,
        user_agent=request.user_agent.string,
        timestamp=datetime.utcnow()
    )
    
    db.session.add(activity)
    db.session.commit()

# Decorator for automatic logging
def log_activity(action):
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            result = f(*args, **kwargs)
            log_user_activity(action, request.url)
            return result
        return decorated_function
    return decorator
```

## 8. Theme System

### Theme Implementation

```javascript
// app/static/js/theme.js
class ThemeManager {
    constructor() {
        this.theme = localStorage.getItem('theme') || 'light';
        this.applyTheme();
    }
    
    applyTheme() {
        document.documentElement.setAttribute('data-theme', this.theme);
        this.updateToggleButton();
    }
    
    toggle() {
        this.theme = this.theme === 'light' ? 'dark' : 'light';
        localStorage.setItem('theme', this.theme);
        this.applyTheme();
    }
    
    updateToggleButton() {
        const btn = document.querySelector('.theme-toggle');
        if (btn) {
            btn.innerHTML = this.theme === 'light' 
                ? '<i class="fas fa-moon"></i>' 
                : '<i class="fas fa-sun"></i>';
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    window.themeManager = new ThemeManager();
});
```

## 9. Performance Optimization

### Caching Implementation

```python
# app/utils/cache.py
from cachetools import TTLCache
import threading

class DataCache:
    def __init__(self):
        self.cache = TTLCache(maxsize=1000, ttl=30)
        self.lock = threading.Lock()
    
    def get_or_fetch(self, key, fetch_func):
        """Get from cache or fetch fresh"""
        with self.lock:
            if key in self.cache:
                return self.cache[key]
            
            data = fetch_func()
            self.cache[key] = data
            return data

# Usage
cache = DataCache()

def get_cached_positions(account_id):
    return cache.get_or_fetch(
        f'positions_{account_id}',
        lambda: fetch_positions_from_api(account_id)
    )
```

## 10. Error Handling

### Global Error Handler

```python
# app/__init__.py
@app.errorhandler(404)
def not_found_error(error):
    return render_template('errors/404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    logger.error(f"Internal error: {error}")
    return render_template('errors/500.html'), 500

@app.errorhandler(Exception)
def handle_exception(error):
    logger.error(f"Unhandled exception: {error}", exc_info=True)
    
    if app.config['DEBUG']:
        raise error
    
    return render_template('errors/500.html'), 500
```

## Testing Features

### Unit Tests

```python
# tests/test_features.py
import unittest
from app import create_app, db
from app.models import User, TradingAccount

class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app('testing')
        self.client = self.app.test_client()
        
    def test_account_creation(self):
        """Test account creation"""
        with self.app.app_context():
            user = User(username='test')
            user.set_password('Test@1234')
            
            account = TradingAccount(
                user_id=user.id,
                account_name='Test Account',
                broker='TEST'
            )
            
            db.session.add(user)
            db.session.add(account)
            db.session.commit()
            
            self.assertIsNotNone(account.id)
    
    def test_websocket_connection(self):
        """Test WebSocket initialization"""
        # Test implementation
        pass
```

## 11. Strategy Builder Implementation

### Strategy Model

```python
# app/models.py
class Strategy(db.Model):
    __tablename__ = 'strategies'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    market_condition = db.Column(db.String(50))  # 'non_expiry', 'expiry', 'any'
    risk_profile = db.Column(db.String(50))  # 'fixed_lots', 'balanced', 'conservative', 'aggressive'

    # Timing settings
    entry_time = db.Column(db.Time)
    exit_time = db.Column(db.Time)
    square_off_time = db.Column(db.Time)

    # Risk management
    max_loss = db.Column(db.Float)
    max_profit = db.Column(db.Float)
    trailing_sl = db.Column(db.Float)
    risk_monitoring_enabled = db.Column(db.Boolean, default=True)
    auto_exit_on_max_loss = db.Column(db.Boolean, default=True)
    auto_exit_on_max_profit = db.Column(db.Boolean, default=True)

    # Supertrend-based exit
    supertrend_exit_enabled = db.Column(db.Boolean, default=False)
    supertrend_exit_type = db.Column(db.String(20))  # 'breakout' or 'breakdown'
    supertrend_period = db.Column(db.Integer, default=7)
    supertrend_multiplier = db.Column(db.Float, default=3.0)
    supertrend_timeframe = db.Column(db.String(10), default='5m')

    # Order settings
    product_order_type = db.Column(db.String(10), default='MIS')  # 'MIS' or 'NRML'
    selected_accounts = db.Column(db.JSON)  # List of account IDs
```

### Strategy Leg Model

```python
class StrategyLeg(db.Model):
    __tablename__ = 'strategy_legs'

    id = db.Column(db.Integer, primary_key=True)
    strategy_id = db.Column(db.Integer, db.ForeignKey('strategies.id'), nullable=False)
    leg_number = db.Column(db.Integer, nullable=False)

    # Instrument details
    instrument = db.Column(db.String(50))  # 'NIFTY', 'BANKNIFTY', 'SENSEX'
    product_type = db.Column(db.String(20))  # 'options', 'futures', 'equity'
    expiry = db.Column(db.String(50))  # 'current_week', 'next_week', 'current_month'
    action = db.Column(db.String(10))  # 'BUY', 'SELL'

    # Option specifics
    option_type = db.Column(db.String(10))  # 'CE', 'PE'
    strike_selection = db.Column(db.String(50))  # 'ATM', 'OTM', 'ITM', 'strike_price', 'premium_near'
    strike_offset = db.Column(db.Integer, default=0)
    strike_price = db.Column(db.Float)
    premium_value = db.Column(db.Float)

    # Order details
    order_type = db.Column(db.String(20))  # 'MARKET', 'LIMIT', 'SL-MKT', 'SL-LMT'
    lots = db.Column(db.Integer, default=1)

    # Exit conditions
    stop_loss_type = db.Column(db.String(20))  # 'percentage', 'points', 'premium'
    stop_loss_value = db.Column(db.Float)
    take_profit_type = db.Column(db.String(20))
    take_profit_value = db.Column(db.Float)
    enable_trailing = db.Column(db.Boolean, default=False)
```

## 12. Supertrend Exit Service (NEW)

### Automated Supertrend-Based Exits

```python
# app/utils/supertrend_exit_service.py
class SupertrendExitService:
    """
    Monitor strategies with Supertrend exit enabled.
    Runs at the start of each minute for candle close detection.
    """

    def __init__(self, scheduler):
        self._scheduler = scheduler

    def start(self):
        """Start Supertrend monitoring"""
        # Run at start of each minute
        self._scheduler.add_job(
            self.check_supertrend_exits,
            'cron',
            minute='*',  # Every minute
            second=2,    # 2 seconds after minute start (ensure candle close)
            id='supertrend_exit_service'
        )
        logger.info("Supertrend Exit Service started")

    def check_supertrend_exits(self):
        """Check all executions with Supertrend exit enabled"""
        executions = StrategyExecution.query.filter(
            StrategyExecution.status == 'active',
            StrategyExecution.supertrend_exit_enabled == True
        ).all()

        for execution in executions:
            try:
                self._check_supertrend_signal(execution)
            except Exception as e:
                logger.error(f"Supertrend check failed for execution {execution.id}: {e}")

    def _check_supertrend_signal(self, execution):
        """Check if Supertrend signal triggers exit"""
        strategy = execution.strategy

        # Get historical data for Supertrend calculation
        historical = self._fetch_historical_data(
            execution.underlying_symbol,
            strategy.supertrend_timeframe,
            periods=100  # Enough for ATR warmup
        )

        if not historical:
            return

        # Calculate Supertrend
        supertrend, direction, _, _ = calculate_supertrend(
            historical['high'],
            historical['low'],
            historical['close'],
            period=strategy.supertrend_period,
            multiplier=strategy.supertrend_multiplier
        )

        # Get current and previous direction
        current_direction = direction[-1]
        prev_direction = direction[-2] if len(direction) > 1 else current_direction

        # Check exit conditions
        exit_type = strategy.supertrend_exit_type

        if exit_type == 'breakout' and prev_direction == 1 and current_direction == -1:
            # Bullish to Bearish - exit breakout strategies
            self._trigger_supertrend_exit(execution, 'breakout', direction[-1])

        elif exit_type == 'breakdown' and prev_direction == -1 and current_direction == 1:
            # Bearish to Bullish - exit breakdown strategies
            self._trigger_supertrend_exit(execution, 'breakdown', direction[-1])

    def _trigger_supertrend_exit(self, execution, exit_type, direction):
        """Execute Supertrend-based exit"""
        logger.warning(
            f"Supertrend exit triggered: {exit_type} for execution {execution.id}, "
            f"direction changed to {direction}"
        )

        # Log risk event
        event = RiskEvent(
            strategy_execution_id=execution.id,
            event_type='supertrend_exit',
            trigger_value=direction,
            threshold_value=0,
            action_taken='exit_initiated',
            details=json.dumps({
                'exit_type': exit_type,
                'timeframe': execution.strategy.supertrend_timeframe,
                'period': execution.strategy.supertrend_period,
                'multiplier': execution.strategy.supertrend_multiplier
            }),
            created_at=datetime.now(timezone('Asia/Kolkata'))
        )
        db.session.add(event)

        # Execute exit
        risk_manager = RiskManager()
        risk_manager._execute_exit_orders(execution)

        execution.status = 'exited'
        execution.exit_reason = 'supertrend_exit'
        db.session.commit()
```

## 13. Database-Driven Trading Hours (NEW)

### Trading Hours Models

```python
# app/models.py
class TradingHoursTemplate(db.Model):
    """Database-driven trading hours configuration"""
    __tablename__ = 'trading_hours_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # 'equity', 'commodity', 'currency'
    market_open = db.Column(db.Time, nullable=False)  # 09:15:00
    market_close = db.Column(db.Time, nullable=False)  # 15:30:00
    pre_open_start = db.Column(db.Time)  # 09:00:00
    pre_open_end = db.Column(db.Time)  # 09:08:00
    is_active = db.Column(db.Boolean, default=True)

class MarketHoliday(db.Model):
    """Track market holidays"""
    __tablename__ = 'market_holidays'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    name = db.Column(db.String(100))
    markets = db.Column(db.JSON)  # ['NSE', 'BSE', 'MCX']

class SpecialTradingSession(db.Model):
    """Special trading sessions (muhurat, extended hours)"""
    __tablename__ = 'special_trading_sessions'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    name = db.Column(db.String(100))
    market_open = db.Column(db.Time, nullable=False)
    market_close = db.Column(db.Time, nullable=False)
```

### Trading Hours Utility

```python
# app/utils/trading_hours.py
class TradingHoursManager:
    """Manage trading hours with database-driven configuration"""

    def __init__(self):
        self._ist = timezone('Asia/Kolkata')

    def is_market_open(self, market='equity'):
        """Check if market is currently open"""
        now = datetime.now(self._ist)
        today = now.date()

        # Check if holiday
        if MarketHoliday.query.filter_by(date=today).first():
            # Check for special session
            special = SpecialTradingSession.query.filter_by(date=today).first()
            if special:
                return self._is_within_hours(now.time(), special.market_open, special.market_close)
            return False

        # Check weekend
        if now.weekday() >= 5:
            return False

        # Get trading hours template
        template = TradingHoursTemplate.query.filter_by(name=market, is_active=True).first()
        if not template:
            return False

        return self._is_within_hours(now.time(), template.market_open, template.market_close)

    def get_next_market_open(self, market='equity'):
        """Get next market open time"""
        now = datetime.now(self._ist)
        template = TradingHoursTemplate.query.filter_by(name=market, is_active=True).first()

        if not template:
            return None

        # Find next trading day
        check_date = now.date()
        for _ in range(7):
            check_date += timedelta(days=1)

            # Skip weekends
            if check_date.weekday() >= 5:
                continue

            # Skip holidays
            if MarketHoliday.query.filter_by(date=check_date).first():
                continue

            return datetime.combine(check_date, template.market_open, tzinfo=self._ist)

        return None

    def _is_within_hours(self, current_time, open_time, close_time):
        """Check if current time is within trading hours"""
        return open_time <= current_time <= close_time
```

## 14. Supertrend Indicator Implementation

### Numba-Optimized Supertrend (Pine Script v6 Compatible)

```python
# app/utils/supertrend.py
import numpy as np
import talib
from numba import njit

def calculate_supertrend(high, low, close, period=7, multiplier=3.0):
    """
    Calculate Supertrend indicator matching Pine Script v6 implementation.
    Uses Numba for performance optimization.
    """
    # Ensure numpy arrays
    high = np.asarray(high, dtype=np.float64)
    low = np.asarray(low, dtype=np.float64)
    close = np.asarray(close, dtype=np.float64)

    # Calculate ATR using TA-Lib (RMA-based, matching Pine Script)
    atr = talib.ATR(high, low, close, timeperiod=period)

    # Calculate basic bands
    hl2 = (high + low) / 2
    basic_upper = hl2 + (multiplier * atr)
    basic_lower = hl2 - (multiplier * atr)

    # Use Numba-optimized core calculation
    upper_band, lower_band, supertrend, direction = _supertrend_core(
        close, basic_upper, basic_lower, atr
    )

    return supertrend, direction, upper_band, lower_band

@njit
def _supertrend_core(close, basic_upper, basic_lower, atr):
    """Numba-optimized core Supertrend calculation"""
    n = len(close)
    upper_band = np.empty(n)
    lower_band = np.empty(n)
    supertrend = np.empty(n)
    direction = np.empty(n, dtype=np.int32)

    # Find first valid index (after ATR warmup)
    first_valid = -1
    for i in range(n):
        if not np.isnan(atr[i]):
            first_valid = i
            break

    if first_valid == -1:
        return upper_band, lower_band, supertrend, direction

    # Initialize first valid bar
    upper_band[first_valid] = basic_upper[first_valid]
    lower_band[first_valid] = basic_lower[first_valid]
    direction[first_valid] = 1  # Start bearish (Pine Script convention)
    supertrend[first_valid] = upper_band[first_valid]

    # Calculate subsequent bars
    for i in range(first_valid + 1, n):
        if np.isnan(atr[i]):
            continue

        prev_upper = upper_band[i - 1]
        prev_lower = lower_band[i - 1]
        prev_close = close[i - 1]

        # Adjust upper band (only if previous was valid)
        if not np.isnan(prev_upper) and basic_upper[i] < prev_upper:
            upper_band[i] = basic_upper[i]
        elif not np.isnan(prev_upper) and prev_close > prev_upper:
            upper_band[i] = basic_upper[i]
        else:
            upper_band[i] = prev_upper if not np.isnan(prev_upper) else basic_upper[i]

        # Adjust lower band
        if not np.isnan(prev_lower) and basic_lower[i] > prev_lower:
            lower_band[i] = basic_lower[i]
        elif not np.isnan(prev_lower) and prev_close < prev_lower:
            lower_band[i] = basic_lower[i]
        else:
            lower_band[i] = prev_lower if not np.isnan(prev_lower) else basic_lower[i]

        # Determine direction
        prev_dir = direction[i - 1]
        if prev_dir == -1 and close[i] > upper_band[i]:
            direction[i] = 1  # Bullish
        elif prev_dir == 1 and close[i] < lower_band[i]:
            direction[i] = -1  # Bearish
        else:
            direction[i] = prev_dir

        # Set supertrend value
        supertrend[i] = lower_band[i] if direction[i] == 1 else upper_band[i]

    return upper_band, lower_band, supertrend, direction
```

## 13. Margin Calculator Implementation

### Dynamic Lot Sizing

```python
# app/utils/margin_calculator.py
class MarginCalculator:
    """Calculate optimal lot sizes based on available margin and risk profile"""

    def calculate_lots_for_strategy(self, user_id, strategy, account_id):
        """
        Calculate lots based on:
        1. Available margin in account
        2. Trade quality grade (A/B/C)
        3. Margin requirement for instrument
        4. Expiry vs non-expiry day
        """
        # Get account funds
        account = TradingAccount.query.get(account_id)
        client = ExtendedOpenAlgoAPI(
            api_key=account.get_api_key(),
            host=account.host_url
        )
        funds = client.funds()
        available_margin = funds.get('availablecash', 0)

        # Get trade quality percentage
        quality_grade = strategy.risk_profile  # 'A', 'B', 'C'
        quality = TradeQuality.query.filter_by(
            user_id=user_id,
            quality_grade=quality_grade
        ).first()

        if not quality:
            TradeQuality.get_or_create_defaults(user_id)
            quality = TradeQuality.query.filter_by(
                user_id=user_id,
                quality_grade=quality_grade
            ).first()

        usable_margin = available_margin * (quality.margin_percentage / 100)

        # Get margin requirement per lot
        is_expiry = self._is_expiry_day()
        margin_per_lot = self._get_margin_requirement(
            user_id,
            strategy.instrument,
            strategy.trade_type,
            is_expiry
        )

        # Calculate lots
        calculated_lots = int(usable_margin / margin_per_lot)

        # Apply freeze quantity limit
        settings = TradingSettings.query.filter_by(
            user_id=user_id,
            symbol=strategy.instrument
        ).first()

        if settings:
            max_lots = settings.max_lots_per_order
            calculated_lots = min(calculated_lots, max_lots)

        return max(1, calculated_lots)

    def _get_margin_requirement(self, user_id, instrument, trade_type, is_expiry):
        """Get margin requirement from user's saved settings"""
        margin_req = MarginRequirement.query.filter_by(
            user_id=user_id,
            instrument=instrument
        ).first()

        if not margin_req:
            MarginRequirement.get_or_create_defaults(user_id)
            margin_req = MarginRequirement.query.filter_by(
                user_id=user_id,
                instrument=instrument
            ).first()

        # Select appropriate margin based on trade type and expiry
        if trade_type == 'ce_pe_sell':
            return margin_req.ce_pe_sell_expiry if is_expiry else margin_req.ce_pe_sell_non_expiry
        elif trade_type == 'ce_and_pe_sell':
            return margin_req.ce_and_pe_sell_expiry if is_expiry else margin_req.ce_and_pe_sell_non_expiry
        elif trade_type == 'futures':
            return margin_req.futures_expiry if is_expiry else margin_req.futures_non_expiry

        return 250000  # Default fallback
```

## 14. Risk Event Tracking

### Risk Event Model

```python
# app/models.py
class RiskEvent(db.Model):
    """Audit log for risk threshold triggers"""
    __tablename__ = 'risk_events'

    id = db.Column(db.Integer, primary_key=True)
    strategy_id = db.Column(db.Integer, db.ForeignKey('strategies.id'), nullable=False)
    execution_id = db.Column(db.Integer, db.ForeignKey('strategy_executions.id'), nullable=True)
    event_type = db.Column(db.String(50), nullable=False)  # 'max_loss', 'max_profit', 'trailing_sl', 'supertrend'
    threshold_value = db.Column(db.Float)  # The threshold that was breached
    current_value = db.Column(db.Float)  # Current P&L or price
    action_taken = db.Column(db.String(50))  # 'close_all', 'close_partial', 'alert_only'
    exit_order_ids = db.Column(db.JSON)  # List of exit orders placed
    triggered_at = db.Column(db.DateTime, default=datetime.utcnow)
    notes = db.Column(db.Text)

    # Relationships
    strategy = db.relationship('Strategy', backref='risk_events')
    execution = db.relationship('StrategyExecution', backref='risk_events')
```

### Risk Event Logging

```python
def log_risk_event(strategy_id, event_type, threshold, current_value, action, order_ids=None):
    """Log a risk threshold breach event"""
    event = RiskEvent(
        strategy_id=strategy_id,
        event_type=event_type,
        threshold_value=threshold,
        current_value=current_value,
        action_taken=action,
        exit_order_ids=order_ids,
        triggered_at=datetime.utcnow()
    )
    db.session.add(event)
    db.session.commit()

    logger.info(f"Risk event logged: {event_type} for strategy {strategy_id}, "
                f"threshold={threshold}, current={current_value}, action={action}")

    return event
```

## 15. Trade Quality Grades

### Trade Quality Model

```python
class TradeQuality(db.Model):
    """Configurable trade quality grades for margin utilization"""
    __tablename__ = 'trade_qualities'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    quality_grade = db.Column(db.String(10), nullable=False)  # 'A', 'B', 'C'
    margin_percentage = db.Column(db.Float, nullable=False)  # 95%, 65%, 36%
    risk_level = db.Column(db.String(20))  # 'conservative', 'moderate', 'aggressive'
    description = db.Column(db.Text)

    @staticmethod
    def get_or_create_defaults(user_id):
        """Create default trade qualities: A=95%, B=65%, C=36%"""
        defaults = [
            {'quality_grade': 'A', 'margin_percentage': 95.0, 'risk_level': 'conservative'},
            {'quality_grade': 'B', 'margin_percentage': 65.0, 'risk_level': 'moderate'},
            {'quality_grade': 'C', 'margin_percentage': 36.0, 'risk_level': 'aggressive'}
        ]

        for default in defaults:
            quality = TradeQuality.query.filter_by(
                user_id=user_id,
                quality_grade=default['quality_grade']
            ).first()

            if not quality:
                quality = TradeQuality(user_id=user_id, **default)
                db.session.add(quality)

        db.session.commit()
```

This comprehensive features implementation guide provides all the necessary code and instructions to build AlgoMirror's complete functionality including strategy building, Supertrend indicator, margin calculation, and risk management.