# AlgoMirror - Database Schema Documentation

## Database Overview

AlgoMirror uses SQLAlchemy ORM with support for both SQLite (development) and PostgreSQL (production). The schema is designed for scalability, data integrity, and efficient querying.

## Schema Evolution (2024 Updates)

### New Tables Added
- **RiskEvent**: Audit trail for automated risk management with IST timestamps
- **WebSocketSession**: On-demand option chain session tracking with 5-minute expiry
- **TradingHoursTemplate**: Database-driven market hours configuration
- **MarketHoliday**: Holiday calendar management
- **SpecialTradingSession**: Muhurat and special session handling

### Enhanced Tables
- **StrategyExecution**: Added `peak_pnl`, `exit_retry_count`, `exit_reason`, `underlying_symbol` for AFL-style trailing stop
- **Strategy**: Added `supertrend_*` fields for technical indicator exits
- **Position**: Added `ltp` field for WebSocket price updates

## Core Tables

### 1. Users Table

```sql
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(80) UNIQUE NOT NULL,
    email VARCHAR(120) UNIQUE NOT NULL,
    password_hash VARCHAR(256) NOT NULL,
    is_admin BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP,
    
    INDEX idx_username (username),
    INDEX idx_email (email)
);
```

**Model Definition:**
```python
class User(UserMixin, db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(256), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    
    # Relationships
    trading_accounts = db.relationship('TradingAccount', backref='user', lazy='dynamic')
    activity_logs = db.relationship('ActivityLog', backref='user', lazy='dynamic')
```

### 2. Trading Accounts Table

```sql
CREATE TABLE trading_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    account_name VARCHAR(100) NOT NULL,
    broker VARCHAR(50) NOT NULL,
    api_key_encrypted TEXT,
    host_url VARCHAR(200) DEFAULT 'http://127.0.0.1:5000',
    websocket_url VARCHAR(200) DEFAULT 'ws://127.0.0.1:8765',
    is_primary BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    last_connected TIMESTAMP,
    connection_status VARCHAR(20) DEFAULT 'disconnected',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_is_primary (is_primary),
    INDEX idx_is_active (is_active)
);
```

**Model Definition:**
```python
class TradingAccount(db.Model):
    __tablename__ = 'trading_accounts'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_name = db.Column(db.String(100), nullable=False)
    broker = db.Column(db.String(50), nullable=False)
    api_key_encrypted = db.Column(db.Text)
    host_url = db.Column(db.String(200), default='http://127.0.0.1:5000')
    websocket_url = db.Column(db.String(200), default='ws://127.0.0.1:8765')
    is_primary = db.Column(db.Boolean, default=False)
    is_active = db.Column(db.Boolean, default=True)
    last_connected = db.Column(db.DateTime)
    connection_status = db.Column(db.String(20), default='disconnected')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    orders = db.relationship('Order', backref='account', lazy='dynamic')
    positions = db.relationship('Position', backref='account', lazy='dynamic')
    holdings = db.relationship('Holding', backref='account', lazy='dynamic')
```

### 3. Orders Table

```sql
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    order_id VARCHAR(50) NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    action VARCHAR(10) NOT NULL,  -- BUY/SELL
    quantity INTEGER NOT NULL,
    order_type VARCHAR(20) NOT NULL,  -- MARKET/LIMIT/SL/SLM
    price DECIMAL(10,2),
    trigger_price DECIMAL(10,2),
    product VARCHAR(10),  -- MIS/CNC/NRML
    status VARCHAR(20) NOT NULL,  -- PENDING/EXECUTED/CANCELLED/REJECTED
    filled_quantity INTEGER DEFAULT 0,
    average_price DECIMAL(10,2),
    placed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    executed_at TIMESTAMP,
    
    FOREIGN KEY (account_id) REFERENCES trading_accounts(id) ON DELETE CASCADE,
    INDEX idx_account_id (account_id),
    INDEX idx_order_id (order_id),
    INDEX idx_symbol (symbol),
    INDEX idx_status (status),
    INDEX idx_placed_at (placed_at)
);
```

**Model Definition:**
```python
class Order(db.Model):
    __tablename__ = 'orders'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('trading_accounts.id'), nullable=False)
    order_id = db.Column(db.String(50), nullable=False)
    symbol = db.Column(db.String(50), nullable=False)
    exchange = db.Column(db.String(10), nullable=False)
    action = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    order_type = db.Column(db.String(20), nullable=False)
    price = db.Column(db.Float)
    trigger_price = db.Column(db.Float)
    product = db.Column(db.String(10))
    status = db.Column(db.String(20), nullable=False)
    filled_quantity = db.Column(db.Integer, default=0)
    average_price = db.Column(db.Float)
    placed_at = db.Column(db.DateTime, default=datetime.utcnow)
    executed_at = db.Column(db.DateTime)
```

### 4. Positions Table

```sql
CREATE TABLE positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    product VARCHAR(10),
    average_price DECIMAL(10,2) NOT NULL,
    current_price DECIMAL(10,2),
    pnl DECIMAL(10,2),
    pnl_percent DECIMAL(5,2),
    day_change DECIMAL(10,2),
    day_change_percent DECIMAL(5,2),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (account_id) REFERENCES trading_accounts(id) ON DELETE CASCADE,
    INDEX idx_account_id (account_id),
    INDEX idx_symbol (symbol),
    UNIQUE KEY unique_position (account_id, symbol, product)
);
```

**Model Definition:**
```python
class Position(db.Model):
    __tablename__ = 'positions'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('trading_accounts.id'), nullable=False)
    symbol = db.Column(db.String(50), nullable=False)
    exchange = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    product = db.Column(db.String(10))
    average_price = db.Column(db.Float, nullable=False)
    current_price = db.Column(db.Float)
    pnl = db.Column(db.Float)
    pnl_percent = db.Column(db.Float)
    day_change = db.Column(db.Float)
    day_change_percent = db.Column(db.Float)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('account_id', 'symbol', 'product', name='unique_position'),
    )
```

### 5. Holdings Table

```sql
CREATE TABLE holdings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    symbol VARCHAR(50) NOT NULL,
    exchange VARCHAR(10) NOT NULL,
    quantity INTEGER NOT NULL,
    average_price DECIMAL(10,2) NOT NULL,
    current_price DECIMAL(10,2),
    pnl DECIMAL(10,2),
    pnl_percent DECIMAL(5,2),
    invested_value DECIMAL(10,2),
    current_value DECIMAL(10,2),
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (account_id) REFERENCES trading_accounts(id) ON DELETE CASCADE,
    INDEX idx_account_id (account_id),
    INDEX idx_symbol (symbol),
    UNIQUE KEY unique_holding (account_id, symbol)
);
```

**Model Definition:**
```python
class Holding(db.Model):
    __tablename__ = 'holdings'
    
    id = db.Column(db.Integer, primary_key=True)
    account_id = db.Column(db.Integer, db.ForeignKey('trading_accounts.id'), nullable=False)
    symbol = db.Column(db.String(50), nullable=False)
    exchange = db.Column(db.String(10), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    average_price = db.Column(db.Float, nullable=False)
    current_price = db.Column(db.Float)
    pnl = db.Column(db.Float)
    pnl_percent = db.Column(db.Float)
    invested_value = db.Column(db.Float)
    current_value = db.Column(db.Float)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        db.UniqueConstraint('account_id', 'symbol', name='unique_holding'),
    )
```

### 6. Activity Log Table

```sql
CREATE TABLE activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action VARCHAR(100) NOT NULL,
    details TEXT,
    ip_address VARCHAR(45),
    user_agent VARCHAR(200),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_action (action),
    INDEX idx_timestamp (timestamp),
    INDEX idx_user_timestamp (user_id, timestamp)
);
```

**Model Definition:**
```python
class ActivityLog(db.Model):
    __tablename__ = 'activity_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    action = db.Column(db.String(100), nullable=False)
    details = db.Column(db.Text)
    ip_address = db.Column(db.String(45))
    user_agent = db.Column(db.String(200))
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    
    __table_args__ = (
        db.Index('idx_user_timestamp', 'user_id', 'timestamp'),
        db.Index('idx_action_timestamp', 'action', 'timestamp'),
    )
```

## Strategy-Related Tables

### 7. Strategies Table

```sql
CREATE TABLE strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    market_condition VARCHAR(50),  -- 'non_expiry', 'expiry', 'any'
    risk_profile VARCHAR(50),  -- 'fixed_lots', 'balanced', 'conservative', 'aggressive'
    is_active BOOLEAN DEFAULT TRUE,
    is_template BOOLEAN DEFAULT FALSE,

    -- Timing settings
    entry_time TIME,
    exit_time TIME,
    square_off_time TIME,

    -- Risk management
    max_loss DECIMAL(10,2),
    max_profit DECIMAL(10,2),
    trailing_sl DECIMAL(10,2),
    risk_monitoring_enabled BOOLEAN DEFAULT TRUE,
    risk_check_interval INTEGER DEFAULT 1,
    auto_exit_on_max_loss BOOLEAN DEFAULT TRUE,
    auto_exit_on_max_profit BOOLEAN DEFAULT TRUE,
    trailing_sl_type VARCHAR(20) DEFAULT 'percentage',

    -- Supertrend-based exit
    supertrend_exit_enabled BOOLEAN DEFAULT FALSE,
    supertrend_exit_type VARCHAR(20),  -- 'breakout' or 'breakdown'
    supertrend_period INTEGER DEFAULT 7,
    supertrend_multiplier DECIMAL(5,2) DEFAULT 3.0,
    supertrend_timeframe VARCHAR(10) DEFAULT '5m',
    supertrend_exit_triggered BOOLEAN DEFAULT FALSE,

    -- Order settings
    product_order_type VARCHAR(10) DEFAULT 'MIS',
    selected_accounts JSON,
    allocation_type VARCHAR(50),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_is_active (is_active)
);
```

**Model Definition:**
```python
class Strategy(db.Model):
    __tablename__ = 'strategies'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text)
    market_condition = db.Column(db.String(50))
    risk_profile = db.Column(db.String(50))

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
    supertrend_exit_type = db.Column(db.String(20))
    supertrend_period = db.Column(db.Integer, default=7)
    supertrend_multiplier = db.Column(db.Float, default=3.0)
    supertrend_timeframe = db.Column(db.String(10), default='5m')

    # Relationships
    legs = db.relationship('StrategyLeg', backref='strategy', lazy='dynamic', cascade='all, delete-orphan')
    executions = db.relationship('StrategyExecution', backref='strategy', lazy='dynamic', cascade='all, delete-orphan')
    risk_events = db.relationship('RiskEvent', backref='strategy')

    @property
    def total_pnl(self):
        """Calculate total P&L from all executions"""
        return sum(e.realized_pnl or 0 for e in self.executions if e.status != 'error')
```

### 8. Strategy Legs Table

```sql
CREATE TABLE strategy_legs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    leg_number INTEGER NOT NULL,

    -- Instrument details
    instrument VARCHAR(50),  -- 'NIFTY', 'BANKNIFTY', 'SENSEX'
    product_type VARCHAR(20),  -- 'options', 'futures', 'equity'
    expiry VARCHAR(50),  -- 'current_week', 'next_week', 'current_month'
    action VARCHAR(10),  -- 'BUY', 'SELL'

    -- Option specifics
    option_type VARCHAR(10),  -- 'CE', 'PE'
    strike_selection VARCHAR(50),  -- 'ATM', 'OTM', 'ITM', 'strike_price', 'premium_near'
    strike_offset INTEGER DEFAULT 0,
    strike_price DECIMAL(10,2),
    premium_value DECIMAL(10,2),

    -- Order details
    order_type VARCHAR(20),  -- 'MARKET', 'LIMIT', 'SL-MKT', 'SL-LMT'
    limit_price DECIMAL(10,2),
    trigger_price DECIMAL(10,2),
    price_condition VARCHAR(10),  -- 'ABOVE' or 'BELOW'
    quantity INTEGER,
    lots INTEGER DEFAULT 1,

    -- Exit conditions
    stop_loss_type VARCHAR(20),
    stop_loss_value DECIMAL(10,2),
    take_profit_type VARCHAR(20),
    take_profit_value DECIMAL(10,2),
    enable_trailing BOOLEAN DEFAULT FALSE,
    trailing_type VARCHAR(20),
    trailing_value DECIMAL(10,2),

    is_executed BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE,
    INDEX idx_strategy_id (strategy_id)
);
```

### 9. Strategy Executions Table (ENHANCED)

The StrategyExecution table has been enhanced to support AFL-style trailing stop-loss, BUY-FIRST exit priority, and Supertrend exits.

```sql
CREATE TABLE strategy_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_id INTEGER NOT NULL,
    account_id INTEGER NOT NULL,
    leg_id INTEGER NOT NULL,

    -- Order details
    order_id VARCHAR(100),
    exit_order_id VARCHAR(100),
    symbol VARCHAR(100),
    exchange VARCHAR(20),
    underlying_symbol VARCHAR(50),  -- NEW: For Supertrend calculation (NIFTY, BANKNIFTY, etc.)
    entry_price DECIMAL(10,2),
    exit_price DECIMAL(10,2),
    quantity INTEGER,
    total_quantity INTEGER,  -- NEW: Total position quantity across all legs

    -- Status tracking
    status VARCHAR(50),  -- 'pending', 'active', 'exited', 'stopped', 'error'
    broker_order_status VARCHAR(50),
    entry_time TIMESTAMP,
    exit_time TIMESTAMP,
    exit_reason VARCHAR(100),  -- 'max_loss', 'max_profit', 'trailing_stop', 'supertrend_exit', 'manual'

    -- P&L tracking
    realized_pnl DECIMAL(10,2),
    unrealized_pnl DECIMAL(10,2),
    brokerage DECIMAL(10,2),
    error_message TEXT,

    -- Risk Management (NEW fields)
    risk_monitoring_enabled BOOLEAN DEFAULT TRUE,
    max_loss_amount DECIMAL(10,2),
    max_profit_amount DECIMAL(10,2),
    trailing_sl_amount DECIMAL(10,2),
    peak_pnl DECIMAL(10,2),  -- NEW: Tracks highest P&L for AFL-style trailing stop
    exit_retry_count INTEGER DEFAULT 0,  -- NEW: Retry counter for failed exits

    -- Supertrend Exit Settings (NEW)
    supertrend_exit_enabled BOOLEAN DEFAULT FALSE,
    supertrend_exit_type VARCHAR(20),  -- 'breakout' or 'breakdown'

    -- Real-time monitoring
    last_price DECIMAL(10,2),
    last_price_updated TIMESTAMP,
    websocket_subscribed BOOLEAN DEFAULT FALSE,

    -- Risk event capture
    sl_hit_at TIMESTAMP,
    sl_hit_price DECIMAL(10,2),
    tp_hit_at TIMESTAMP,
    tp_hit_price DECIMAL(10,2),

    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (strategy_id) REFERENCES strategies(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES trading_accounts(id) ON DELETE CASCADE,
    FOREIGN KEY (leg_id) REFERENCES strategy_legs(id) ON DELETE CASCADE,
    INDEX idx_strategy_execution_status (status),
    INDEX idx_strategy_execution_active (status, risk_monitoring_enabled)
);
```

**Model Definition (Enhanced):**
```python
class StrategyExecution(db.Model):
    __tablename__ = 'strategy_executions'

    id = db.Column(db.Integer, primary_key=True)
    strategy_id = db.Column(db.Integer, db.ForeignKey('strategies.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('trading_accounts.id'), nullable=False)

    # Position tracking
    underlying_symbol = db.Column(db.String(50))  # For Supertrend calculation
    total_quantity = db.Column(db.Integer)
    status = db.Column(db.String(50))  # 'pending', 'active', 'exited', 'error'
    exit_reason = db.Column(db.String(100))

    # Risk Management
    risk_monitoring_enabled = db.Column(db.Boolean, default=True)
    max_loss_amount = db.Column(db.Float)
    max_profit_amount = db.Column(db.Float)
    trailing_sl_amount = db.Column(db.Float)
    peak_pnl = db.Column(db.Float)  # For AFL-style trailing stop
    exit_retry_count = db.Column(db.Integer, default=0)

    # Supertrend Exit
    supertrend_exit_enabled = db.Column(db.Boolean, default=False)
    supertrend_exit_type = db.Column(db.String(20))

    # Relationships
    legs = db.relationship('ExecutionLeg', backref='execution', lazy='dynamic')
    risk_events = db.relationship('RiskEvent', backref='execution')

    __table_args__ = (
        db.Index('idx_strategy_execution_status', 'status'),
        db.Index('idx_strategy_execution_active', 'status', 'risk_monitoring_enabled'),
    )
```

**AFL-Style Trailing Stop Logic:**
```
Initial Stop = -trailing_sl_amount
Peak P&L = max(current_pnl, previous_peak)
Trailing Stop Level = Initial Stop + Peak P&L (when peak > 0)
Exit when: current_pnl <= Trailing Stop Level
```

## Margin & Risk Management Tables

### 10. Margin Requirements Table

```sql
CREATE TABLE margin_requirements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    instrument VARCHAR(50) NOT NULL,  -- 'NIFTY', 'BANKNIFTY', 'SENSEX'

    -- Margin values for different trade types (in INR per lot)
    ce_pe_sell_expiry DECIMAL(12,2) DEFAULT 205000,
    ce_pe_sell_non_expiry DECIMAL(12,2) DEFAULT 250000,
    ce_and_pe_sell_expiry DECIMAL(12,2) DEFAULT 250000,
    ce_and_pe_sell_non_expiry DECIMAL(12,2) DEFAULT 320000,
    futures_expiry DECIMAL(12,2) DEFAULT 215000,
    futures_non_expiry DECIMAL(12,2) DEFAULT 215000,

    -- SENSEX specific margins
    sensex_ce_pe_sell_expiry DECIMAL(12,2) DEFAULT 180000,
    sensex_ce_pe_sell_non_expiry DECIMAL(12,2) DEFAULT 220000,
    sensex_ce_and_pe_sell_expiry DECIMAL(12,2) DEFAULT 225000,
    sensex_ce_and_pe_sell_non_expiry DECIMAL(12,2) DEFAULT 290000,
    sensex_futures_expiry DECIMAL(12,2) DEFAULT 185000,
    sensex_futures_non_expiry DECIMAL(12,2) DEFAULT 185000,

    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (user_id, instrument)
);
```

### 11. Trade Quality Grades Table

```sql
CREATE TABLE trade_qualities (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    quality_grade VARCHAR(10) NOT NULL,  -- 'A', 'B', 'C'
    margin_percentage DECIMAL(5,2) NOT NULL,  -- 95%, 65%, 36%
    risk_level VARCHAR(20),  -- 'conservative', 'moderate', 'aggressive'
    description TEXT,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (user_id, quality_grade)
);
```

**Default Values:**
- Grade A: 95% margin utilization (conservative)
- Grade B: 65% margin utilization (moderate)
- Grade C: 36% margin utilization (aggressive)

### 12. Margin Tracker Table

```sql
CREATE TABLE margin_trackers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,

    -- Available margins
    total_available_margin DECIMAL(12,2) DEFAULT 0,
    used_margin DECIMAL(12,2) DEFAULT 0,
    free_margin DECIMAL(12,2) DEFAULT 0,

    -- F&O specific margins
    span_margin DECIMAL(12,2) DEFAULT 0,
    exposure_margin DECIMAL(12,2) DEFAULT 0,
    option_premium DECIMAL(12,2) DEFAULT 0,

    -- Trade-wise margin allocation
    allocated_margins JSON,

    -- Real-time tracking
    last_updated TIMESTAMP,
    update_count INTEGER DEFAULT 0,

    FOREIGN KEY (account_id) REFERENCES trading_accounts(id) ON DELETE CASCADE
);
```

### 13. Risk Events Table (ENHANCED)

The RiskEvent table provides comprehensive audit logging for automated risk management actions with IST (Asia/Kolkata) timestamps.

```sql
CREATE TABLE risk_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    strategy_execution_id INTEGER NOT NULL,  -- Changed from strategy_id
    event_type VARCHAR(50) NOT NULL,  -- 'max_loss', 'max_profit', 'trailing_stop', 'supertrend_exit'
    trigger_value DECIMAL(12,2),  -- P&L value that triggered the event
    threshold_value DECIMAL(12,2),  -- Configured threshold
    action_taken VARCHAR(100),  -- 'exit_initiated', 'exit_completed', 'exit_failed', 'retry_limit_exceeded'
    details TEXT,  -- JSON with full context (error messages, retry count, etc.)
    created_at TIMESTAMP NOT NULL,  -- IST timezone (Asia/Kolkata)

    FOREIGN KEY (strategy_execution_id) REFERENCES strategy_executions(id) ON DELETE CASCADE,
    INDEX idx_risk_event_execution (strategy_execution_id),
    INDEX idx_risk_event_type_time (event_type, created_at)
);
```

**Model Definition:**
```python
from pytz import timezone

IST = timezone('Asia/Kolkata')

class RiskEvent(db.Model):
    """Audit log for risk management events with IST timestamps"""
    __tablename__ = 'risk_events'

    id = db.Column(db.Integer, primary_key=True)
    strategy_execution_id = db.Column(db.Integer, db.ForeignKey('strategy_executions.id'), nullable=False)
    event_type = db.Column(db.String(50), nullable=False)
    trigger_value = db.Column(db.Float)  # P&L value that triggered
    threshold_value = db.Column(db.Float)  # Configured threshold
    action_taken = db.Column(db.String(100))
    details = db.Column(db.Text)  # JSON with context
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(IST))

    # Relationships
    execution = db.relationship('StrategyExecution', backref='risk_events')

    __table_args__ = (
        db.Index('idx_risk_event_execution', 'strategy_execution_id'),
        db.Index('idx_risk_event_type_time', 'event_type', 'created_at'),
    )
```

**Event Types:**
| Event Type | Description | Trigger Condition |
|------------|-------------|-------------------|
| `max_loss` | Maximum loss threshold breached | P&L <= -max_loss_amount |
| `max_profit` | Profit target reached | P&L >= max_profit_amount |
| `trailing_stop` | AFL-style trailing stop triggered | P&L <= trailing_stop_level |
| `supertrend_exit` | Technical indicator exit signal | Supertrend direction change |

### 14. Trading Settings Table

```sql
CREATE TABLE trading_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    symbol VARCHAR(50) NOT NULL,  -- 'NIFTY', 'BANKNIFTY', 'SENSEX'
    lot_size INTEGER NOT NULL DEFAULT 25,
    freeze_quantity INTEGER NOT NULL DEFAULT 1800,
    max_lots_per_order INTEGER DEFAULT 36,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    UNIQUE (user_id, symbol)
);
```

**Default Values (as of May 2025):**
- NIFTY: lot_size=75, freeze_quantity=1800, max_lots_per_order=24
- BANKNIFTY: lot_size=35, freeze_quantity=900, max_lots_per_order=25
- SENSEX: lot_size=20, freeze_quantity=1000, max_lots_per_order=50

### 15. WebSocket Sessions Table (ENHANCED)

The WebSocketSession table manages on-demand option chain sessions with 5-minute auto-expiry.

```sql
CREATE TABLE websocket_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id VARCHAR(64) UNIQUE NOT NULL,
    user_id INTEGER NOT NULL,
    account_id INTEGER,
    session_type VARCHAR(50),  -- 'option_chain', 'position_monitor'
    instrument VARCHAR(50),  -- NIFTY, BANKNIFTY, SENSEX
    symbol_count INTEGER DEFAULT 0,  -- Number of symbols subscribed
    is_active BOOLEAN DEFAULT TRUE,
    last_heartbeat TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP,  -- Auto-expires after 5 minutes of inactivity

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (account_id) REFERENCES trading_accounts(id) ON DELETE SET NULL,
    INDEX idx_ws_session_active (is_active, expires_at),
    INDEX idx_ws_session_user (user_id, is_active)
);
```

**Model Definition:**
```python
class WebSocketSession(db.Model):
    """Track on-demand WebSocket sessions for option chains"""
    __tablename__ = 'websocket_sessions'

    id = db.Column(db.Integer, primary_key=True)
    session_id = db.Column(db.String(64), unique=True, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    account_id = db.Column(db.Integer, db.ForeignKey('trading_accounts.id'))
    session_type = db.Column(db.String(50))  # 'option_chain', 'position_monitor'
    instrument = db.Column(db.String(50))  # NIFTY, BANKNIFTY, SENSEX
    symbol_count = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    last_heartbeat = db.Column(db.DateTime)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    expires_at = db.Column(db.DateTime)

    __table_args__ = (
        db.Index('idx_ws_session_active', 'is_active', 'expires_at'),
        db.Index('idx_ws_session_user', 'user_id', 'is_active'),
    )
```

**Session Lifecycle:**
1. Created when user visits option chain page (on-demand, not at market open)
2. Heartbeat extends expiry by 5 minutes on user activity
3. Auto-expires after 5 minutes of inactivity
4. Cleanup job removes expired sessions periodically

## Configuration Tables (NEW)

### 16. Trading Hours Template Table

Database-driven trading hours replace hardcoded market times.

```sql
CREATE TABLE trading_hours_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(50) NOT NULL,  -- 'equity', 'commodity', 'currency'
    market_open TIME NOT NULL,  -- 09:15:00
    market_close TIME NOT NULL,  -- 15:30:00
    pre_open_start TIME,  -- 09:00:00
    pre_open_end TIME,  -- 09:08:00
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Model Definition:**
```python
class TradingHoursTemplate(db.Model):
    """Database-driven trading hours configuration"""
    __tablename__ = 'trading_hours_templates'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)  # 'equity', 'commodity', 'currency'
    market_open = db.Column(db.Time, nullable=False)
    market_close = db.Column(db.Time, nullable=False)
    pre_open_start = db.Column(db.Time)
    pre_open_end = db.Column(db.Time)
    is_active = db.Column(db.Boolean, default=True)
```

**Default Values:**
| Market | Open | Close | Pre-Open |
|--------|------|-------|----------|
| Equity | 09:15 | 15:30 | 09:00-09:08 |
| Commodity | 09:00 | 23:30 | - |
| Currency | 09:00 | 17:00 | - |

### 17. Market Holidays Table

```sql
CREATE TABLE market_holidays (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL UNIQUE,
    name VARCHAR(100),
    markets JSON,  -- ['NSE', 'BSE', 'MCX']

    INDEX idx_holiday_date (date)
);
```

**Model Definition:**
```python
class MarketHoliday(db.Model):
    """Track market holidays"""
    __tablename__ = 'market_holidays'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False, unique=True)
    name = db.Column(db.String(100))
    markets = db.Column(db.JSON)  # ['NSE', 'BSE', 'MCX']
```

### 18. Special Trading Sessions Table

```sql
CREATE TABLE special_trading_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    name VARCHAR(100),
    market_open TIME NOT NULL,
    market_close TIME NOT NULL,

    INDEX idx_special_session_date (date)
);
```

**Model Definition:**
```python
class SpecialTradingSession(db.Model):
    """Special trading sessions (muhurat, extended hours)"""
    __tablename__ = 'special_trading_sessions'

    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, nullable=False)
    name = db.Column(db.String(100))
    market_open = db.Column(db.Time, nullable=False)
    market_close = db.Column(db.Time, nullable=False)
```

**Example: Muhurat Trading**
```python
special_session = SpecialTradingSession(
    date=date(2024, 11, 1),  # Diwali
    name='Muhurat Trading',
    market_open=time(18, 15),
    market_close=time(19, 15)
)
```

## WebSocket & Failover Tables

### 12. WebSocket Connections Table

```sql
CREATE TABLE websocket_connections (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL,
    connection_id VARCHAR(100) UNIQUE,
    status VARCHAR(20) DEFAULT 'disconnected',
    connected_at TIMESTAMP,
    disconnected_at TIMESTAMP,
    messages_received INTEGER DEFAULT 0,
    last_heartbeat TIMESTAMP,
    
    FOREIGN KEY (account_id) REFERENCES trading_accounts(id) ON DELETE CASCADE,
    INDEX idx_account_id (account_id),
    INDEX idx_status (status)
);
```

### 13. Failover Events Table

```sql
CREATE TABLE failover_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    from_account_id INTEGER,
    to_account_id INTEGER,
    reason VARCHAR(100),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    success BOOLEAN DEFAULT TRUE,
    error_message TEXT,
    
    FOREIGN KEY (from_account_id) REFERENCES trading_accounts(id) ON DELETE SET NULL,
    FOREIGN KEY (to_account_id) REFERENCES trading_accounts(id) ON DELETE SET NULL,
    INDEX idx_timestamp (timestamp)
);
```

## Database Migrations

### Using Flask-Migrate

```bash
# Initialize migrations
flask db init

# Create a new migration
flask db migrate -m "Add new table"

# Apply migrations
flask db upgrade

# Rollback migrations
flask db downgrade
```

### Migration Example

```python
"""Add trading_accounts table

Revision ID: 001
Create Date: 2024-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa

def upgrade():
    op.create_table('trading_accounts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('account_name', sa.String(100), nullable=False),
        sa.Column('broker', sa.String(50), nullable=False),
        sa.Column('api_key_encrypted', sa.Text()),
        sa.Column('host_url', sa.String(200)),
        sa.Column('websocket_url', sa.String(200)),
        sa.Column('is_primary', sa.Boolean(), default=False),
        sa.Column('is_active', sa.Boolean(), default=True),
        sa.Column('created_at', sa.DateTime()),
        sa.Column('updated_at', sa.DateTime()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_index('idx_user_id', 'trading_accounts', ['user_id'])
    op.create_index('idx_is_primary', 'trading_accounts', ['is_primary'])

def downgrade():
    op.drop_index('idx_is_primary', 'trading_accounts')
    op.drop_index('idx_user_id', 'trading_accounts')
    op.drop_table('trading_accounts')
```

## Database Optimization

### 1. Indexes

```sql
-- Composite indexes for common queries
CREATE INDEX idx_orders_account_status ON orders(account_id, status);
CREATE INDEX idx_positions_account_symbol ON positions(account_id, symbol);
CREATE INDEX idx_activity_user_action ON activity_logs(user_id, action);

-- Covering indexes for performance
CREATE INDEX idx_accounts_user_primary ON trading_accounts(user_id, is_primary) 
    INCLUDE (account_name, broker);
```

### 2. Query Optimization

```python
# Efficient query with joins
def get_user_positions_summary(user_id):
    return db.session.query(
        TradingAccount.account_name,
        func.count(Position.id).label('position_count'),
        func.sum(Position.pnl).label('total_pnl')
    ).join(
        Position, TradingAccount.id == Position.account_id
    ).filter(
        TradingAccount.user_id == user_id
    ).group_by(
        TradingAccount.id
    ).all()
```

### 3. Connection Pooling

```python
# config.py
SQLALCHEMY_ENGINE_OPTIONS = {
    'pool_size': 10,
    'pool_recycle': 3600,
    'pool_pre_ping': True,
    'max_overflow': 20
}
```

## Database Maintenance

### 1. Regular Tasks

```sql
-- Cleanup old activity logs (keep 90 days)
DELETE FROM activity_logs 
WHERE timestamp < datetime('now', '-90 days');

-- Archive old orders (move to archive table)
INSERT INTO orders_archive 
SELECT * FROM orders 
WHERE placed_at < datetime('now', '-30 days');

DELETE FROM orders 
WHERE placed_at < datetime('now', '-30 days');
```

### 2. Backup Strategy

```bash
# SQLite backup
sqlite3 instance/algomirror.db ".backup backup/algomirror_$(date +%Y%m%d).db"

# PostgreSQL backup
pg_dump -U username -d algomirror > backup/algomirror_$(date +%Y%m%d).sql
```

### 3. Performance Monitoring

```sql
-- Check table sizes
SELECT 
    table_name,
    pg_size_pretty(pg_total_relation_size(table_name::regclass)) AS size
FROM information_schema.tables
WHERE table_schema = 'public'
ORDER BY pg_total_relation_size(table_name::regclass) DESC;

-- Find slow queries
SELECT 
    query,
    calls,
    mean_exec_time,
    total_exec_time
FROM pg_stat_statements
ORDER BY mean_exec_time DESC
LIMIT 10;
```

## Data Integrity

### 1. Constraints

```python
# Ensure data integrity with constraints
class TradingAccount(db.Model):
    __table_args__ = (
        db.CheckConstraint('length(account_name) >= 3', name='check_account_name_length'),
        db.CheckConstraint("broker IN ('Zerodha', 'Upstox', 'AngelOne', ...)", name='check_valid_broker'),
        db.UniqueConstraint('user_id', 'account_name', name='unique_user_account'),
    )
```

### 2. Triggers

```sql
-- Update timestamp trigger
CREATE TRIGGER update_timestamp
AFTER UPDATE ON trading_accounts
FOR EACH ROW
BEGIN
    UPDATE trading_accounts 
    SET updated_at = CURRENT_TIMESTAMP 
    WHERE id = NEW.id;
END;
```

### 3. Foreign Key Actions

```python
# Cascade deletes for related data
account_id = db.Column(
    db.Integer, 
    db.ForeignKey('trading_accounts.id', ondelete='CASCADE'),
    nullable=False
)
```

This comprehensive database schema documentation provides the complete structure for AlgoMirror's data persistence layer.