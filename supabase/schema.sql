-- ─────────────────────────────────────────────────────────
-- ForecastAI V2 — Supabase Schema (Lean Version)
-- Only stores what truly needs persistence.
-- Price history, forecasts, OHLCV → fetched live from yfinance.
-- ─────────────────────────────────────────────────────────

-- Users table: store accounts
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    username        VARCHAR(50) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

-- Research reports: worth keeping (historical sentiment trends)
CREATE TABLE IF NOT EXISTS research_reports (
    id              BIGSERIAL PRIMARY KEY,
    ticker          VARCHAR(20) NOT NULL,
    sentiment       VARCHAR(20) DEFAULT 'NEUTRAL',
    confidence      DECIMAL(4,3),
    sentiment_score DECIMAL(4,3),
    summary         TEXT,
    key_factors     JSONB DEFAULT '[]',
    recommendation  TEXT,
    risk_level      VARCHAR(10),
    source          VARCHAR(50),
    news_count      INT DEFAULT 0,
    created_at      TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_research_ticker_time
    ON research_reports(ticker, created_at DESC);

-- Paper trades: linked to a specific user
CREATE TABLE IF NOT EXISTS paper_trades (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT REFERENCES users(id) ON DELETE CASCADE,
    ticker       VARCHAR(20) NOT NULL,
    action       VARCHAR(10) NOT NULL CHECK (action IN ('BUY','SELL')),
    quantity     DECIMAL(18,8),
    price        DECIMAL(18,4),
    total_value  DECIMAL(18,4),
    model_signal VARCHAR(30),
    trade_time   TIMESTAMPTZ DEFAULT NOW()
);

-- Admin config/User portfolios: unique per user
CREATE TABLE IF NOT EXISTS admin_config (
    id               SERIAL PRIMARY KEY,
    user_id          BIGINT UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    initial_balance  DECIMAL(18,4) DEFAULT 10000,
    current_balance  DECIMAL(18,4) DEFAULT 10000,
    total_pnl        DECIMAL(18,4) DEFAULT 0,
    win_trades       INT DEFAULT 0,
    loss_trades      INT DEFAULT 0,
    is_running       BOOLEAN DEFAULT FALSE,
    started_at       TIMESTAMPTZ,
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Model accuracy log: track forecast quality over time (optional)
CREATE TABLE IF NOT EXISTS model_accuracy (
    id             BIGSERIAL PRIMARY KEY,
    ticker         VARCHAR(20) NOT NULL,
    model_name     VARCHAR(50),
    forecast_date  DATE,
    predicted_price DECIMAL(18,4),
    actual_price   DECIMAL(18,4),
    error_pct      DECIMAL(6,2),
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

-- REMOVED TABLES (no longer needed — all fetched live):
-- ✗ price_history   → yfinance real-time
-- ✗ forecasts       → computed on-demand per request
-- ✗ news_cache      → fetched fresh each time (30min in-memory cache only)
