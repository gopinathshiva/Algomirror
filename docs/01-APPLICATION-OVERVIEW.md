# AlgoMirror - Complete Application Overview

## Executive Summary

AlgoMirror is an enterprise-grade multi-account management platform for OpenAlgo that enables traders to manage multiple trading accounts from 24+ different brokers through a unified interface. The platform provides real-time WebSocket integration with automatic failover, on-demand option chain monitoring, automated risk management with real-time position tracking, and enterprise security features.

## Core Capabilities

### 1. Multi-Account Management
- **Unified Dashboard**: Manage unlimited trading accounts from 24+ brokers
- **Account Hierarchy**: Primary/Secondary account designation with automatic failover
- **Cross-Broker Support**: Seamless switching between different broker APIs
- **Real-time Synchronization**: Live updates across all connected accounts
- **Multi-Account Strategy Execution**: Execute strategies across multiple accounts simultaneously

### 2. Advanced Trading Features
- **Option Chain Monitoring**: On-demand NIFTY, BANKNIFTY & SENSEX option chains with market depth
- **WebSocket Streaming**: Professional-grade real-time data with automatic reconnection and failover
- **Order Management**: Place, modify, and cancel orders across multiple accounts
- **Position Tracking**: Real-time P&L calculation via WebSocket with batch database updates
- **Holdings Analysis**: Long-term portfolio tracking with performance metrics
- **Strategy Builder**: Visual strategy builder with multi-leg support
- **Supertrend Indicator**: Pine Script v6 compatible technical analysis with Numba optimization
- **Automated Risk Management**: Real-time max loss/profit targets, AFL-style trailing stop-loss, and Supertrend-based exits

### 3. Real-Time Monitoring Infrastructure (NEW)
- **Position Monitor**: WebSocket-based position tracking for open positions only (5-50 symbols vs 1000+)
- **Risk Manager**: Automated 5-second risk checks with threshold enforcement
- **Order Status Poller**: Background order tracking with fill notifications
- **Session Manager**: On-demand option chain sessions with 5-minute auto-expiry

### 4. Enterprise Security
- **Zero-Trust Architecture**: No default accounts, first user becomes admin
- **Military-Grade Encryption**: AES-128 encryption for all API keys
- **Multi-Tier Rate Limiting**: Protection against abuse and DoS attacks
- **Comprehensive Audit Logging**: Complete activity trail including risk events

### 5. High Availability Features
- **Automatic Failover**: Multi-level failover (WebSocket -> Account -> Broker)
- **Connection Pooling**: Single shared WebSocket for all services
- **Health Monitoring**: Continuous connection health checks with auto-recovery
- **Trading Hours Management**: Database-driven scheduling with holiday support
- **Graceful Degradation**: Falls back to API polling if WebSocket unavailable

## Technology Stack

### Backend
- **Framework**: Flask 2.3+ with Blueprint architecture
- **Database**: SQLAlchemy ORM with SQLite (dev) / PostgreSQL (production)
- **WebSocket**: Native WebSocket client with enterprise failover features
- **Encryption**: Cryptography library with Fernet symmetric encryption
- **Authentication**: Flask-Login with secure session management
- **Technical Analysis**: TA-Lib with Numba-optimized Supertrend implementation
- **Threading**: Native Python threading (gthread worker for Gunicorn)
- **Scheduling**: APScheduler with IST timezone support

### Frontend
- **CSS Framework**: Tailwind CSS + DaisyUI (OpenAlgo theme)
- **JavaScript**: Vanilla JS for WebSocket client and real-time updates
- **Build System**: NPM with PostCSS for Tailwind compilation
- **Theme System**: Light/Dark mode matching OpenAlgo design

### Infrastructure
- **Rate Limiting**: Flask-Limiter with Redis backend (production)
- **Session Storage**: Configurable - filesystem (single-user) or database sessions
- **Background Services**: Position Monitor, Risk Manager, Order Poller, Session Manager
- **Logging**: Structured JSON logging with IST timestamps

## Project Structure

```
Algomirror/
├── app/                      # Main application package
│   ├── __init__.py          # Flask app factory and service initialization
│   ├── models.py            # SQLAlchemy database models
│   ├── auth/                # Authentication blueprint
│   │   ├── routes.py        # Login, register, password management
│   │   └── forms.py         # WTForms with validation
│   ├── main/                # Main blueprint
│   │   └── routes.py        # Dashboard and landing pages
│   ├── accounts/            # Account management blueprint
│   │   └── routes.py        # CRUD operations for trading accounts
│   ├── trading/             # Trading operations blueprint
│   │   └── routes.py        # Orders, positions, holdings views
│   ├── api/                 # RESTful API blueprint
│   │   └── routes.py        # JSON endpoints for data retrieval
│   ├── utils/               # Utility modules
│   │   ├── openalgo_client.py       # Extended OpenAlgo API client
│   │   ├── websocket_manager.py     # Professional WebSocket with failover
│   │   ├── background_service.py    # Core service orchestration
│   │   ├── position_monitor.py      # Real-time position tracking (NEW)
│   │   ├── risk_manager.py          # Automated risk enforcement (NEW)
│   │   ├── order_status_poller.py   # Background order polling (NEW)
│   │   ├── session_manager.py       # On-demand option chain sessions (NEW)
│   │   ├── option_chain.py          # Option chain management
│   │   ├── rate_limiter.py          # Rate limiting decorators
│   │   ├── lot_sizing_engine.py     # Position sizing calculations
│   │   ├── supertrend.py            # Numba-optimized Supertrend indicator
│   │   ├── supertrend_exit_service.py  # Supertrend exit monitoring
│   │   ├── margin_calculator.py     # Dynamic margin and lot calculation
│   │   ├── strategy_executor.py     # Parallel strategy execution engine
│   │   └── compat.py                # Cross-platform threading (NEW)
│   ├── strategy/            # Strategy blueprint (builder, execution)
│   ├── margin/              # Margin management blueprint
│   └── templates/           # Jinja2 HTML templates
│       ├── base.html        # Core layout with theme system
│       ├── layout.html      # Extended layout for pages
│       └── trading/         # Trading-specific templates
├── migrations/              # Database migration files
├── docs/                    # Documentation
├── logs/                    # Application logs
├── instance/                # Instance-specific files
├── src/                     # Source CSS for Tailwind
├── tests/                   # Test files including failover tests
├── requirements.txt         # Python dependencies
├── pyproject.toml          # UV/pip project configuration
├── package.json            # Node dependencies
├── tailwind.config.js      # Tailwind configuration
├── config.py               # Application configuration
├── wsgi.py                 # WSGI entry point
├── init_db.py              # Database initialization
└── .env.example            # Environment variables template
```

## Background Services Architecture

### Services Started at Application Startup

1. **Position Monitor** (`position_monitor.py`)
   - Subscribes ONLY to symbols with open positions (5-50 vs 1000+)
   - WebSocket-based real-time price updates
   - Batch database writes every 2 seconds
   - Graceful degradation to API polling if WebSocket unavailable

2. **Risk Manager** (`risk_manager.py`)
   - Runs every 5 seconds via APScheduler
   - Enforces max loss, max profit, and trailing stop-loss thresholds
   - AFL-style trailing stop-loss with peak tracking
   - BUY-FIRST exit priority (closes SELL positions before BUY)
   - Automatic retry mechanism for failed exits

3. **Order Status Poller** (`order_status_poller.py`)
   - Background polling of pending orders
   - Rate-limit aware (1 req/sec/account)
   - Parallel polling across different accounts
   - Callbacks to Position Monitor on order fills

4. **Session Manager** (`session_manager.py`)
   - Manages on-demand option chain sessions
   - 5-minute auto-expiry with heartbeat mechanism
   - Reduces WebSocket subscriptions dramatically

5. **Supertrend Exit Service** (`supertrend_exit_service.py`)
   - Monitors strategies with Supertrend exit enabled
   - Runs at start of each minute for candle close detection
   - Supports breakout and breakdown exit types

### Shared WebSocket Manager
- Single shared WebSocket connection for all services
- Prevents broker connection limits (AngelOne limits to 1-2 per API key)
- Automatic failover to backup accounts
- Zero-value protection (caches last valid price)

## Key Architectural Decisions

### 1. No Default Accounts
The system intentionally has NO default admin accounts. The first registered user automatically becomes admin through runtime detection. This zero-trust approach eliminates common security vulnerabilities.

### 2. Blueprint Architecture
Flask blueprints provide modular organization with independent routing, making the codebase maintainable and allowing teams to work on different features independently.

### 3. Encrypted Storage
All sensitive data (API keys) are encrypted at rest using Fernet symmetric encryption. Keys are only decrypted in-memory during API calls.

### 4. On-Demand Option Chains
Option chains load ONLY when users visit the option chain page, not automatically at market open. This dramatically reduces WebSocket subscriptions from 1000+ to just active positions.

### 5. WebSocket Failover Strategy
Three-tier failover ensures continuous operation:
- Level 1: WebSocket reconnection with exponential backoff (base=2s, max=60s)
- Level 2: Account failover (switch to backup account)
- Level 3: Graceful degradation to REST API polling

### 6. Local Asset Serving
All CSS and JavaScript assets are compiled and served locally, eliminating CDN dependencies and ensuring reliability in restricted network environments.

### 7. Database-Driven Trading Hours
Trading hours, holidays, and special sessions are stored in database tables (`TradingHoursTemplate`, `MarketHoliday`, `SpecialTradingSession`) instead of hardcoded values.

## Development Workflow

### 1. Initial Setup (Using UV - Recommended)
```bash
# Clone repository
git clone <repository-url>
cd Algomirror

# Install UV (if not already installed)
pip install uv

# Create and activate virtual environment
uv venv
.venv\Scripts\activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Install dependencies (10-100x faster than pip)
uv pip install -e .

# Install Node dependencies and build CSS
npm install
npm run build-css

# Configure environment
cp .env.example .env
# Edit .env with your settings

# Initialize database
uv run init_db.py

# Run application
uv run wsgi.py
```

### 2. Development Mode
```bash
# Watch CSS changes
npm run watch-css

# Run with debug mode
uv run wsgi.py  # Runs on http://localhost:8000
```

### 3. Database Management
```bash
# Create migration
flask db migrate -m "Description"

# Apply migration
flask db upgrade

# Reset database
python init_db.py reset

# Create test data
python init_db.py testdata
```

## Integration Points

### 1. OpenAlgo API
- REST API: Default http://127.0.0.1:5000
- WebSocket: Default ws://127.0.0.1:8765
- Authentication: API key-based
- Ping endpoint for connection testing

### 2. Broker Support
Supports 24+ brokers including:
- Zerodha, Angel One, Upstox, Groww
- Dhan, Fyers, 5paisa, Aliceblue
- IIFL XTS, Kotak Securities, Paytm
- Compositedge XTS, Definedge, Firstock
- Flattrade, IndiaBulls, IndMoney
- Motilal Oswal, Pocketful, Shoonya
- Tradejini, Wisdom Capital XTS, Zebu

### 3. Market Data
- On-demand option chain for NIFTY, BANKNIFTY & SENSEX
- Market depth with bid/ask spreads
- Live position P&L via WebSocket
- Historical data for Supertrend calculations

## Performance Optimizations

### 1. Reduced API Calls
- **Before**: 100+ API calls/minute for price fetching
- **After**: ~5 calls/minute (only on WebSocket stall)
- **Mechanism**: 5-second cache + WebSocket primary source

### 2. Reduced WebSocket Subscriptions
- **Before**: 1000+ symbols (all option chain strikes)
- **After**: 5-50 symbols (only open positions)
- **Mechanism**: On-demand option chain loading via SessionManager

### 3. Batch Database Writes
- Position Monitor queues price updates
- Flushes in batch every 2 seconds
- Single transaction per flush instead of 100s per second

### 4. Rate Limit Compliance
- Parallel polling across accounts (different accounts parallelized)
- Sequential within same account (respects 1 req/sec)
- Thread pool with max 10 workers

## Security Implementation

### 1. Authentication
- Secure password hashing with Werkzeug (pbkdf2:sha256)
- Session-based authentication with secure cookies
- CSRF protection on all forms
- Strong password policy enforcement

### 2. Authorization
- Single-user application (first user becomes admin)
- Account-level isolation
- API key encryption at rest
- Audit logging for compliance

### 3. Network Security
- HTTPS enforcement (production)
- Content Security Policy
- XSS and injection protection
- Rate limiting and DDoS protection

## Monitoring & Maintenance

### 1. Logging System
- Structured JSON logging with IST timestamps
- Rotating file handlers (Unix) / Simple file handler (Windows)
- Module-level filtering (noisy modules at WARNING level)
- Performance metrics tracking

### 2. Health Checks
- WebSocket connection monitoring every 30 seconds
- Account availability checks
- Database connection pooling with pre-ping
- Risk manager heartbeat every 5 seconds

### 3. Alerting
- Connection failure notifications in logs
- Rate limit breach alerts
- Risk event logging with full audit trail
- Failover event tracking

## Production Deployment

### 1. Requirements
- PostgreSQL database
- Redis for rate limiting (optional)
- HTTPS with SSL certificates
- Reverse proxy (Nginx/Apache)
- WSGI server (Gunicorn with gthread worker)

### 2. Environment Variables
```bash
FLASK_ENV=production
SECRET_KEY=<strong-random-key>
DATABASE_URL=postgresql://...
REDIS_URL=redis://...  # Optional
ENCRYPTION_KEY=<base64-encoded-key>
SESSION_TYPE=filesystem  # or sqlalchemy
```

### 3. Deployment Steps
1. Set up PostgreSQL
2. Configure environment variables
3. Run database migrations
4. Set up Nginx reverse proxy
5. Configure Gunicorn with gthread workers
6. Set up SSL certificates
7. Configure monitoring and backups

## Strategy & Risk Management Features

### Strategy Builder
- **Visual Builder**: Multi-leg strategy construction
- **Instrument Support**: NIFTY, BANKNIFTY, SENSEX options and futures
- **Strike Selection**: ATM, ITM, OTM with configurable offsets, or premium-based selection
- **Risk Profiles**: Fixed lots, Conservative (40%), Balanced (65%), Aggressive (80%)

### Automated Risk Management (ENHANCED)
- **Max Loss/Profit Targets**: Strategy-level limits with automatic exits
- **AFL-Style Trailing Stop Loss**: Ratcheting stop that only moves up
  - Activates when P&L becomes positive
  - Tracks peak P&L achieved
  - Stop level = Initial Stop + Peak P&L
  - Exits when current_pnl <= trailing_stop
- **Supertrend Exits**: Technical indicator-based exit signals
- **Risk Event Logging**: Complete audit trail with IST timestamps
- **BUY-FIRST Exit Priority**: Closes SELL positions before BUY positions
- **Retry Mechanism**: Automatic retry for failed exit orders

### Margin Calculator
- **Dynamic Lot Sizing**: Calculate optimal lots based on available margin
- **Trade Quality Grades**: A (95%), B (65%), C (36%) margin utilization
- **Expiry Awareness**: Different margin requirements for expiry vs non-expiry days
- **Freeze Quantity Handling**: Automatic order splitting for large positions

## WebSocket Failover Timing

| Parameter | Value | Description |
|-----------|-------|-------------|
| Heartbeat interval | 30 seconds | Health check frequency |
| Max reconnect attempts | 3 | Before account failover |
| Base backoff delay | 2 seconds | Exponential backoff start |
| Max backoff delay | 60 seconds | Maximum wait between retries |
| Post-connect stabilization | 2 seconds | Wait after successful connect |
| Reconnect check interval | 30 seconds | Background service check |

**Failover Timeline**:
- Best case: ~2-4 seconds (immediate switch + stabilization)
- Worst case (3 retries): ~9-11 seconds

## Support & Maintenance

### Regular Tasks
- Monitor WebSocket connections via logs
- Review risk event audit logs
- Update broker configurations as needed
- Database backups
- Security updates

### Troubleshooting
- Check logs in `logs/algomirror.log`
- Verify WebSocket connectivity via connection status
- Test account connections with ping API
- Monitor rate limiting metrics
- Review failover history in logs

## License

Copyright 2024 OpenFlare Technologies. All Rights Reserved.
This is proprietary software. Unauthorized copying, modification, or distribution is prohibited.
