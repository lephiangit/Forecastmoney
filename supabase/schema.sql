-- ─────────────────────────────────────────────────────────
-- ForecastAI V2 — Supabase Schema (Lean Version)
-- Only stores what truly needs persistence.
-- Price history, forecasts, OHLCV → fetched live from yfinance.
-- ─────────────────────────────────────────────────────────

-- Users table: store accounts
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    username        VARCHAR(100) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20) DEFAULT 'user',
    status          VARCHAR(20) DEFAULT 'active',
    last_active     TIMESTAMPTZ DEFAULT NOW(),
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
    id               BIGSERIAL PRIMARY KEY,
    user_id          BIGINT REFERENCES users(id) ON DELETE CASCADE UNIQUE,
    initial_balance  DECIMAL(18,4) DEFAULT 0.0,
    current_balance  DECIMAL(18,4) DEFAULT 0.0,
    total_pnl        DECIMAL(18,4) DEFAULT 0.0,
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

-- Forecast Cache Table
-- Stores heavy API responses for 6 hours to speed up repeated queries.
CREATE TABLE IF NOT EXISTS forecast_cache (
    id            BIGSERIAL PRIMARY KEY,
    ticker        VARCHAR(20) NOT NULL,
    days          INT NOT NULL,
    response_json JSONB NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

-- Index for fast lookup by ticker and days
CREATE INDEX IF NOT EXISTS idx_forecast_cache_lookup 
    ON forecast_cache(ticker, days, created_at DESC);


-- User Watchlists Table
-- Stores personalized watchlists for authenticated users.
CREATE TABLE IF NOT EXISTS user_watchlists (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticker     VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, ticker) -- Prevent duplicate tickers for the same user
);

-- Index for quick retrieval of a user's watchlist
CREATE INDEX IF NOT EXISTS idx_user_watchlists_user_id 
    ON user_watchlists(user_id);


-- ─────────────────────────────────────────────────────────
-- Safe Migration Block (Run this to update existing tables)
-- ─────────────────────────────────────────────────────────
DO $$
BEGIN
    -- Update users table
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='role') THEN
        ALTER TABLE users ADD COLUMN role VARCHAR(20) DEFAULT 'user';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='status') THEN
        ALTER TABLE users ADD COLUMN status VARCHAR(20) DEFAULT 'active';
    END IF;
    IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='last_active') THEN
        ALTER TABLE users ADD COLUMN last_active TIMESTAMPTZ DEFAULT NOW();
    END IF;

    -- Update admin_config table defaults to 0 as requested
    ALTER TABLE admin_config ALTER COLUMN initial_balance SET DEFAULT 0.0;
    ALTER TABLE admin_config ALTER COLUMN current_balance SET DEFAULT 0.0;
END $$;

-- ─────────────────────────────────────────────────────────
-- Row Level Security (RLS)
-- We use FastAPI for auth and the backend uses the service_role key to bypass RLS.
-- Enabling RLS with no policies effectively blocks all direct `anon` key access from the frontend,
-- which secures the DB from unauthorized public API requests.
-- ─────────────────────────────────────────────────────────
ALTER TABLE users ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_reports ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_trades ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_config ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_accuracy ENABLE ROW LEVEL SECURITY;
ALTER TABLE forecast_cache ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_watchlists ENABLE ROW LEVEL SECURITY;