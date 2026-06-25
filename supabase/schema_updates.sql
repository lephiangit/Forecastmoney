-- ==========================================
-- ForecastAI V2 - Feature Additions
-- Run these commands in your Supabase SQL Editor
-- ==========================================

-- 1. Forecast Cache Table
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


-- 2. User Watchlists Table
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
