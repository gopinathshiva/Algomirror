# AlgoMirror - Technical Architecture Guide

## System Architecture Overview

AlgoMirror follows a modular, microservice-ready architecture with clear separation of concerns, enabling scalability, maintainability, and high availability. The system uses a single shared WebSocket connection with on-demand option chain loading and real-time position monitoring.

## Core Architecture Components

### 1. Application Layer Architecture

```
+----------------------------------------------------------+
|                    Web Interface                          |
|            (HTML/CSS/JavaScript + WebSocket)              |
+------------------------------+----------------------------+
                               |
+------------------------------v----------------------------+
|                 Flask Application                         |
|  +-----------------------------------------------------+ |
|  |              Blueprint Architecture                  | |
|  +----------+----------+----------+----------+---------+ |
|  |   Auth   |   Main   | Trading  | Accounts | Strategy| |
|  |  Routes  |  Routes  |  Routes  |  Routes  |  Routes | |
|  +----------+----------+----------+----------+---------+ |
+------------------------------+----------------------------+
                               |
+------------------------------v----------------------------+
|                   Service Layer                           |
|  +--------------+ +--------------+ +--------------+      |
|  |  WebSocket   | | Option Chain | |   OpenAlgo   |      |
|  |   Manager    | |   Manager    | |    Client    |      |
|  +--------------+ +--------------+ +--------------+      |
|  +--------------+ +--------------+ +--------------+      |
|  |  Strategy    | |   Margin     | |  Supertrend  |      |
|  |  Executor    | |  Calculator  | |    Service   |      |
|  +--------------+ +--------------+ +--------------+      |
+------------------------------+----------------------------+
                               |
+------------------------------v----------------------------+
|               Background Services Layer                   |
|  +--------------+ +--------------+ +--------------+      |
|  |  Position    | |    Risk      | | Order Status |      |
|  |   Monitor    | |   Manager    | |    Poller    |      |
|  +--------------+ +--------------+ +--------------+      |
|  +--------------+ +--------------+                       |
|  |   Session    | | Supertrend   |                       |
|  |   Manager    | | Exit Service |                       |
|  +--------------+ +--------------+                       |
+------------------------------+----------------------------+
                               |
+------------------------------v----------------------------+
|                  Data Access Layer                        |
|  +--------------+ +--------------+ +--------------+      |
|  |  SQLAlchemy  | |    Redis     | |  Encryption  |      |
|  |     ORM      | |    Cache     | |   Service    |      |
|  +--------------+ +--------------+ +--------------+      |
+----------------------------------------------------------+
```

### 2. WebSocket Architecture with Failover

```
+----------------------------------------------------------+
|              Professional WebSocket Manager               |
+----------------------------------------------------------+
|                                                          |
|  +-------------------+                                   |
|  | Connection Pool   |                                   |
|  +-------------------+                                   |
|  | Primary Account   +---> Active WebSocket Connection   |
|  +-------------------+                                   |
|  | Backup Account 1  +---> (Standby - 60s cooldown)      |
|  +-------------------+                                   |
|  | Backup Account 2  +---> (Standby)                     |
|  +-------------------+                                   |
|                                                          |
|  +----------------------------------------+              |
|  |         Failover Controller            |              |
|  +----------------------------------------+              |
|  | - Connection Health Monitor            |              |
|  | - Exponential Backoff (2s base, 60s max)|             |
|  | - Account Priority Queue               |              |
|  | - Subscription State Manager           |              |
|  | - Zero-Value Protection (cache LTP)    |              |
|  +----------------------------------------+              |
|                                                          |
|  +----------------------------------------+              |
|  |        Data Processing Pipeline        |              |
|  +----------------------------------------+              |
|  | LTP Handler   -> Position P&L Updates  |              |
|  | Quote Handler -> OHLCV Data            |              |
|  | Depth Handler -> Option Chain Depth    |              |
|  +----------------------------------------+              |
+----------------------------------------------------------+
```

### 3. Background Services Architecture

```
+----------------------------------------------------------+
|           Background Service Orchestration                |
|              (OptionChainBackgroundService)               |
+----------------------------------------------------------+
|                                                          |
|  Shared WebSocket Manager (Singleton)                    |
|  +------------------------------------------------------+|
|  | - Single connection for all services                 ||
|  | - Prevents broker connection limits                  ||
|  | - Non-blocking initialization                        ||
|  +------------------------------------------------------+|
|                                                          |
|  APScheduler Jobs (IST Timezone)                         |
|  +------------------------------------------------------+|
|  | Risk Manager Check    | Every 5 seconds              ||
|  | Session Cleanup       | Every 1 minute               ||
|  | WebSocket Reconnect   | Every 30 seconds             ||
|  | Cache Refresh         | Daily at 5 AM IST            ||
|  +------------------------------------------------------+|
|                                                          |
|  Service Instances                                       |
|  +------------------------------------------------------+|
|  | Position Monitor  | Subscribes to open positions     ||
|  | Risk Manager      | Enforces SL/TP/TSL thresholds    ||
|  | Order Poller      | Tracks pending order fills       ||
|  | Session Manager   | On-demand option chain sessions  ||
|  | Supertrend Exit   | Technical indicator exits        ||
|  +------------------------------------------------------+|
+----------------------------------------------------------+
```

### 4. Position Monitoring Flow

```
+----------------------------------------------------------+
|              Position Monitor Architecture                |
+----------------------------------------------------------+
|                                                          |
|  Entry Order Filled                                      |
|       |                                                  |
|       v                                                  |
|  OrderStatusPoller.on_order_filled()                     |
|       |                                                  |
|       v                                                  |
|  PositionMonitor.subscribe_position(symbol)              |
|       |                                                  |
|       v                                                  |
|  WebSocket Quote Handler receives price                  |
|       |                                                  |
|       v                                                  |
|  Price Update Queue (batched)                            |
|       |                                                  |
|       v (every 2 seconds)                                |
|  Batch Database Write                                    |
|       |                                                  |
|       v                                                  |
|  Risk Manager reads cached prices                        |
|       |                                                  |
|       v (if threshold breached)                          |
|  close_strategy_positions() with BUY-FIRST priority     |
|       |                                                  |
|       v                                                  |
|  PositionMonitor.on_position_closed(symbol)              |
|       |                                                  |
|       v                                                  |
|  Unsubscribe from WebSocket                              |
+----------------------------------------------------------+
```

### 5. Risk Management Flow

```
+----------------------------------------------------------+
|              Risk Manager Architecture                    |
+----------------------------------------------------------+
|                                                          |
|  Every 5 seconds (APScheduler)                           |
|       |                                                  |
|       v                                                  |
|  check_risk_for_all_strategies()                         |
|       |                                                  |
|       v                                                  |
|  For each active strategy with risk_monitoring_enabled:  |
|  +------------------------------------------------------+|
|  | 1. Get current P&L (WebSocket > API > Cache)         ||
|  | 2. Check Max Loss threshold                          ||
|  | 3. Check Max Profit threshold                        ||
|  | 4. Check Trailing Stop Loss                          ||
|  |    - AFL-style ratcheting                            ||
|  |    - Peak tracking                                   ||
|  |    - Only moves up, never down                       ||
|  +------------------------------------------------------+|
|       |                                                  |
|       v (if threshold breached)                          |
|  Log RiskEvent with IST timestamp                        |
|       |                                                  |
|       v                                                  |
|  close_strategy_positions()                              |
|  +------------------------------------------------------+|
|  | Phase 1: Close SELL positions (place BUY orders)     ||
|  | Phase 2: Close BUY positions (place SELL orders)     ||
|  | Retry mechanism for failed exits (max 3 attempts)    ||
|  +------------------------------------------------------+|
+----------------------------------------------------------+
```

### 6. Database Schema Architecture

```sql
-- Core Tables
Users
+-- id (PK)
+-- username (unique)
+-- email (unique)
+-- password_hash
+-- is_admin (boolean)
+-- created_at

TradingAccounts
+-- id (PK)
+-- user_id (FK -> Users)
+-- account_name
+-- broker
+-- api_key_encrypted
+-- host_url
+-- websocket_url
+-- is_primary (boolean)
+-- is_active (boolean)

-- Strategy Tables
Strategy
+-- id (PK)
+-- user_id (FK -> Users)
+-- name
+-- risk_profile ('fixed_lots', 'balanced', 'conservative', 'aggressive')
+-- max_loss / max_profit / trailing_sl
+-- risk_monitoring_enabled (default=True)
+-- auto_exit_on_max_loss / auto_exit_on_max_profit
+-- trailing_sl_type / trailing_sl_active / trailing_sl_peak_pnl
+-- supertrend_exit_enabled / supertrend_exit_type
+-- supertrend_period / supertrend_multiplier / supertrend_timeframe
+-- selected_accounts (JSON)

StrategyLeg
+-- id (PK)
+-- strategy_id (FK -> Strategy)
+-- leg_number
+-- instrument / product_type / expiry / action
+-- option_type / strike_selection / strike_offset
+-- order_type / lots
+-- stop_loss_type / stop_loss_value
+-- take_profit_type / take_profit_value

StrategyExecution
+-- id (PK)
+-- strategy_id (FK -> Strategy)
+-- account_id (FK -> TradingAccounts)
+-- leg_id (FK -> StrategyLeg)
+-- order_id / exit_order_id
+-- status ('pending', 'entered', 'exited', 'stopped', 'error')
+-- entry_price / exit_price / quantity
+-- realized_pnl / unrealized_pnl
+-- last_price / last_price_updated / websocket_subscribed
+-- trailing_sl_triggered / sl_hit_at / tp_hit_at

-- Risk & Audit Tables
RiskEvent
+-- id (PK)
+-- strategy_id (FK -> Strategy)
+-- execution_id (FK -> StrategyExecution, nullable)
+-- event_type ('max_loss', 'max_profit', 'trailing_sl', 'supertrend')
+-- threshold_value / current_value
+-- action_taken / exit_order_ids (JSON)
+-- triggered_at (IST timestamp)
+-- notes

-- Session Management
WebSocketSession
+-- id (PK)
+-- user_id (FK -> Users)
+-- session_id (unique)
+-- underlying / expiry
+-- subscribed_symbols (JSON)
+-- is_active / last_heartbeat
+-- created_at / expires_at (5-minute auto-expiry)

-- Trading Hours (Database-Driven)
TradingHoursTemplate
+-- id (PK)
+-- name / timezone / is_active

TradingSession
+-- id (PK)
+-- template_id (FK -> TradingHoursTemplate)
+-- day_of_week (0=Monday)
+-- pre_market_start / market_open / market_close / post_market_end

MarketHoliday
+-- id (PK)
+-- template_id (FK -> TradingHoursTemplate)
+-- date / description / holiday_type

SpecialTradingSession
+-- id (PK)
+-- template_id (FK -> TradingHoursTemplate)
+-- date / session_type ('muhurat', etc.)
+-- start_time / end_time
```

### 7. Security Architecture

```
+------------------------------------------+
|         Security Layer Stack             |
+------------------------------------------+
|                                          |
|  Application Security                    |
|  +-- Zero-Trust Architecture             |
|  +-- No Default Accounts                 |
|  +-- First User = Admin                  |
|                                          |
|  Data Security                           |
|  +-- Fernet Encryption (AES-128)         |
|  +-- In-Memory Decryption Only           |
|  +-- Secure Key Management               |
|                                          |
|  Network Security                        |
|  +-- HTTPS Enforcement                   |
|  +-- CSRF Protection                     |
|  +-- Content Security Policy             |
|  +-- XSS Prevention                      |
|                                          |
|  Access Control                          |
|  +-- Session-Based Auth                  |
|  +-- Rate Limiting (Multi-Tier)          |
|  +-- API Key Validation                  |
|  +-- Audit Logging (RiskEvent, Activity) |
+------------------------------------------+
```

## Detailed Component Architecture

### Strategy Execution Architecture

```
+----------------------------------------------------------+
|                  Strategy Executor                        |
+----------------------------------------------------------+
|                                                          |
|  +-----------------------------------------------------+ |
|  |              Parallel Execution Engine              | |
|  |  - ThreadPoolExecutor for concurrent order placement| |
|  |  - Max workers configurable per strategy            | |
|  |  - Freeze quantity order splitting                  | |
|  +-----------------------------------------------------+ |
|                                                          |
|  +-----------------------------------------------------+ |
|  |              Margin Calculator                      | |
|  |  - Dynamic lot sizing based on available margin     | |
|  |  - Trade quality grades (A: 95%, B: 65%, C: 36%)    | |
|  |  - Expiry vs non-expiry margin awareness            | |
|  +-----------------------------------------------------+ |
|                                                          |
|  +-----------------------------------------------------+ |
|  |              Risk Monitor Integration               | |
|  |  - Auto-registers with OrderStatusPoller            | |
|  |  - Callbacks to PositionMonitor on fills            | |
|  |  - WebSocket subscription for real-time P&L         | |
|  +-----------------------------------------------------+ |
|                                                          |
|  +-----------------------------------------------------+ |
|  |              Supertrend Exit Service                | |
|  |  - Background thread monitoring price action        | |
|  |  - Numba-optimized Supertrend calculation           | |
|  |  - Automatic exit on breakout/breakdown signals     | |
|  +-----------------------------------------------------+ |
+----------------------------------------------------------+
```

### 1. Flask Application Factory Pattern

```python
# app/__init__.py structure
def create_app(config_name='development'):
    app = Flask(__name__)

    # Configuration
    app.config.from_object(config[config_name])

    # Extensions
    db.init_app(app)
    login_manager.init_app(app)
    limiter.init_app(app)

    # Blueprints
    from app.auth import auth_bp
    from app.main import main_bp
    from app.trading import trading_bp
    from app.accounts import accounts_bp
    from app.api import api_bp
    from app.strategy import strategy_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(main_bp, url_prefix='/')
    app.register_blueprint(trading_bp, url_prefix='/trading')
    app.register_blueprint(accounts_bp, url_prefix='/accounts')
    app.register_blueprint(api_bp, url_prefix='/api')
    app.register_blueprint(strategy_bp, url_prefix='/strategy')

    # Start background services
    with app.app_context():
        from app.utils.background_service import OptionChainBackgroundService
        bg_service = OptionChainBackgroundService.get_instance()
        bg_service.start(app)

    return app
```

### 2. WebSocket Manager Architecture

```python
class ProfessionalWebSocketManager:
    """
    Core Components:
    1. Connection Pool Management
    2. Failover Controller
    3. Data Processor
    4. Subscription Manager
    5. Health Monitor
    6. Zero-Value Protection
    """

    def __init__(self):
        # Connection Management
        self.connection_pool = {}
        self.max_connections = 10
        self.heartbeat_interval = 30

        # Failover Strategy
        self.reconnect_attempts = 3
        self.backoff_strategy = ExponentialBackoff(base=2, max_delay=60)
        self.account_failover_enabled = True

        # Data Processing
        self.data_processor = WebSocketDataProcessor()

        # Subscription State
        self.subscriptions = set()

        # Zero-Value Protection
        self.ltp_cache = {}  # Cache last valid LTP per symbol

        # Threading
        self._lock = threading.Lock()
```

### 3. Position Monitor Architecture

```python
class PositionMonitor:
    """
    Monitors open positions via WebSocket for real-time P&L.
    Subscribes ONLY to symbols with open positions (5-50 vs 1000+).
    """

    def __init__(self):
        self.subscribed_symbols = set()
        self.price_update_queue = Queue()
        self.flush_interval = 2  # seconds

    def subscribe_position(self, symbol, execution_id):
        """Subscribe to WebSocket for position monitoring"""
        if symbol not in self.subscribed_symbols:
            self.websocket_manager.subscribe(symbol, mode='quote')
            self.subscribed_symbols.add(symbol)

    def on_position_closed(self, symbol, execution_id):
        """Unsubscribe when position is closed"""
        self.websocket_manager.unsubscribe(symbol)
        self.subscribed_symbols.discard(symbol)

    def _batch_flush(self):
        """Flush price updates to database every 2 seconds"""
        # Single transaction for all updates
        pass
```

### 4. Risk Manager Architecture

```python
class RiskManager:
    """
    Enforces risk thresholds:
    - Max Loss
    - Max Profit
    - AFL-style Trailing Stop Loss
    """

    def __init__(self):
        self.position_cache = TTLCache(maxsize=1000, ttl=5)

    def check_risk_for_strategy(self, strategy):
        """Called every 5 seconds by scheduler"""
        current_pnl = self._get_current_pnl(strategy)

        # Max Loss Check
        if strategy.max_loss and current_pnl <= -abs(strategy.max_loss):
            self._trigger_exit(strategy, 'max_loss', current_pnl)

        # Max Profit Check
        if strategy.max_profit and current_pnl >= strategy.max_profit:
            self._trigger_exit(strategy, 'max_profit', current_pnl)

        # Trailing Stop Loss (AFL-style)
        if strategy.trailing_sl:
            self._check_trailing_sl(strategy, current_pnl)

    def _check_trailing_sl(self, strategy, current_pnl):
        """AFL-style ratcheting stop loss"""
        if current_pnl > 0:
            if not strategy.trailing_sl_active:
                strategy.trailing_sl_active = True
                strategy.trailing_sl_peak_pnl = current_pnl
            else:
                # Update peak (only moves up)
                if current_pnl > strategy.trailing_sl_peak_pnl:
                    strategy.trailing_sl_peak_pnl = current_pnl

                # Check stop level
                stop_level = -strategy.trailing_sl + strategy.trailing_sl_peak_pnl
                if current_pnl <= stop_level:
                    self._trigger_exit(strategy, 'trailing_sl', current_pnl)
```

### 5. Rate Limiting Architecture

```python
# Multi-tier rate limiting strategy
rate_limits = {
    'global': '1000/minute',
    'auth': '10/minute',
    'api': '100/minute',
    'heavy': '20/minute'
}

# Decorator implementation
@auth_rate_limit()  # 10 req/min for auth endpoints
@api_rate_limit()   # 100 req/min for API endpoints
@heavy_rate_limit() # 20 req/min for heavy operations
```

## Data Flow Architecture

### 1. Real-Time Data Flow

```
User Request -> Flask Route -> Service Layer -> OpenAlgo API
                    |
              WebSocket Stream (shared)
                    |
            Data Processor -> Position Monitor
                    |
            Price Update Queue -> Batch DB Write
                    |
            Risk Manager -> Check Thresholds
                    |
            Client WebSocket -> Real-time UI Updates
```

### 2. Failover Data Flow

```
Primary WebSocket Failure
        |
Exponential Backoff Retry (3 attempts)
        |
Account Failover Decision
        |
60-second cooldown on failed account
        |
Switch to Backup Account
        |
Resubscribe All Active Positions
        |
Resume Data Flow
```

### 3. Option Chain Data Flow (On-Demand)

```
User visits /trading/option-chain
        |
SessionManager.create_session()
        |
Calculate ATM & Strike Range
        |
Subscribe via Shared WebSocket (Depth Mode)
        |
Process Market Depth Updates
        |
Update In-Memory Cache
        |
Broadcast to Connected Clients
        |
Session expires after 5 minutes without heartbeat
        |
Unsubscribe all option chain symbols
```

### 4. Risk Exit Flow

```
Risk Threshold Breached
        |
Log RiskEvent (IST timestamp)
        |
close_strategy_positions()
        |
Phase 1: Identify SELL positions
        |
Place BUY orders to close SELL positions
        |
Phase 2: Identify BUY positions
        |
Place SELL orders to close BUY positions
        |
Track exit orders via OrderStatusPoller
        |
Retry failed exits (max 3 attempts)
        |
Update execution status to 'exited'
        |
PositionMonitor.on_position_closed()
```

## Performance Architecture

### 1. Caching Strategy

```python
# Three-tier caching
cache_layers = {
    'L1': 'In-Memory (TTLCache)',     # 5 second TTL for positions
    'L2': 'Redis Cache',               # 5 minute TTL (optional)
    'L3': 'Database',                  # Persistent storage
}

# Position cache implementation
class RiskManager:
    def __init__(self):
        self.position_cache = TTLCache(maxsize=1000, ttl=5)
```

### 2. Connection Pool Management

```python
# Database connection pooling
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
    'max_overflow': 20,
    'pool_timeout': 30
}

# WebSocket - Single Shared Connection
websocket_config = {
    'max_connections': 1,  # Single shared connection
    'heartbeat_interval': 30,
    'reconnect_attempts': 3,
    'backoff_base': 2,
    'backoff_max': 60
}
```

### 3. Batch Processing

```python
class PositionMonitor:
    """Batch database writes for performance"""

    def __init__(self):
        self.price_update_queue = Queue()
        self.flush_interval = 2  # seconds

    def _flush_price_updates(self):
        """Single transaction for all queued updates"""
        updates = []
        while not self.price_update_queue.empty():
            updates.append(self.price_update_queue.get())

        if updates:
            with db.session.begin():
                for update in updates:
                    # Bulk update
                    pass
```

## Scalability Architecture

### 1. Single-Instance Deployment (Current)

```
Gunicorn (gthread worker, 4 workers)
        |
   Flask Application
        |
   SQLite/PostgreSQL
```

### 2. Future: Horizontal Scaling

```
Load Balancer (Nginx)
        |
+--------+--------+--------+
| App    | App    | App    |
| Server | Server | Server |
| 1      | 2      | 3      |
+--------+--------+--------+
        |
   Shared Redis (sessions + cache)
        |
   PostgreSQL (connection pooling)
```

## Deployment Architecture

### 1. Development Environment

```yaml
Services:
  - Flask Development Server (port 8000)
  - SQLite Database (file-based)
  - In-memory rate limiting
  - Local WebSocket connections
  - Debug logging enabled
```

### 2. Production Environment

```yaml
Services:
  - Gunicorn WSGI Server (gthread worker, 4 workers)
  - PostgreSQL Database (connection pooling)
  - Redis (rate limiting, optional caching)
  - Nginx Reverse Proxy (SSL termination)
  - Structured JSON logging

Background Services (integrated, not separate):
  - Position Monitor (daemon thread)
  - Risk Manager (APScheduler job, every 5s)
  - Order Status Poller (daemon thread)
  - Session Manager (cleanup every 1 min)
  - Supertrend Exit Service (daemon thread)
```

### Threading Architecture

```
+----------------------------------------------------------+
|                    Main Application                       |
+----------------------------------------------------------+
|                                                          |
|  Main Thread (Flask/Gunicorn gthread worker)             |
|  +-- HTTP Request Handlers                               |
|                                                          |
|  Background Daemon Threads:                              |
|  +-- WebSocket Manager Thread                            |
|  |   +-- Connection monitoring & reconnection            |
|  +-- Position Monitor Thread                             |
|  |   +-- Batch price update flushing                     |
|  +-- Order Status Poller Thread                          |
|  |   +-- Periodic order status synchronization           |
|  +-- Supertrend Exit Service Thread                      |
|      +-- Price monitoring for indicator-based exits      |
|                                                          |
|  APScheduler Jobs (non-blocking):                        |
|  +-- Risk Manager (every 5 seconds)                      |
|  +-- Session Cleanup (every 1 minute)                    |
|  +-- WebSocket Reconnect Check (every 30 seconds)        |
|                                                          |
|  Note: Uses native Python threading (not eventlet)       |
|  Compatible with Python 3.13+ and TA-Lib                 |
+----------------------------------------------------------+
```

## Monitoring Architecture

### 1. Application Monitoring

```python
metrics = {
    'websocket_connection_status': gauge,
    'active_positions': gauge,
    'risk_checks_per_minute': counter,
    'failover_events': counter,
    'database_pool_size': gauge
}
```

### 2. Logging Strategy

```python
# JSON structured logging with IST timestamps
logging_config = {
    'format': 'JSON',
    'timezone': 'Asia/Kolkata',
    'rotation': '10MB (Unix) / None (Windows)',
    'noisy_modules': ['websocket_manager', 'background_service'],
    'noisy_level': 'WARNING'
}
```

### 3. Health Checks

```python
health_checks = {
    'websocket_reconnect': 'every 30 seconds',
    'risk_manager': 'every 5 seconds',
    'database_pre_ping': 'every connection',
    'session_cleanup': 'every 1 minute'
}
```

## Security Architecture Details

### 1. Encryption Implementation

```python
from cryptography.fernet import Fernet

class EncryptionService:
    def __init__(self):
        self.cipher = Fernet(self.get_or_create_key())

    def encrypt(self, data: str) -> bytes:
        return self.cipher.encrypt(data.encode())

    def decrypt(self, encrypted_data: bytes) -> str:
        return self.cipher.decrypt(encrypted_data).decode()
```

### 2. Authentication Flow

```
Login Request
     |
Validate Credentials (pbkdf2:sha256)
     |
Create Session
     |
Set Secure Cookie (HTTPOnly, Secure, SameSite)
     |
Return CSRF Token
```

## Best Practices & Patterns

### 1. Design Patterns Used
- **Factory Pattern**: Flask app creation
- **Singleton Pattern**: WebSocket manager, Background services
- **Observer Pattern**: OrderStatusPoller callbacks
- **Strategy Pattern**: Failover strategies
- **Decorator Pattern**: Rate limiting

### 2. SOLID Principles
- **Single Responsibility**: Each service has one purpose
- **Open/Closed**: Extensible via blueprints
- **Liskov Substitution**: Broker interfaces
- **Interface Segregation**: Minimal interfaces
- **Dependency Inversion**: Service abstractions

### 3. Code Organization
- Clear separation of concerns
- Modular blueprint architecture
- Reusable utility functions
- Comprehensive error handling
- Consistent naming conventions

## Testing Architecture

### 1. Test Files

```
tests/
+-- test_models.py
+-- test_websocket_failover.py
+-- test_immediate_failover.py
+-- test_live_failover.py
+-- test_websocket_connection.py
+-- test_option_chain_websocket.py
+-- test_single_websocket.py
```

### 2. Integration Testing

```python
# Test WebSocket failover
# Test account switching
# Test risk threshold triggers
# Test order status polling
# Test position monitoring
```

## Maintenance & Operations

### 1. Database Migrations

```bash
# Alembic migration workflow
flask db init
flask db migrate -m "Add new column"
flask db upgrade
flask db downgrade
```

### 2. Backup Strategy

```yaml
Backup Schedule:
  - Database: Daily automated backups
  - Configuration: Version controlled
  - Logs: Rotated and archived
  - Encryption keys: Secure backup
```

This architecture ensures AlgoMirror remains scalable, maintainable, and reliable while providing enterprise-grade features for multi-account trading management with real-time risk monitoring.
