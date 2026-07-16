-- ─────────────────────────────────────────────────────────
-- ForecastAI V2 — Supabase Schema (Final Optimized Version)
-- ─────────────────────────────────────────────────────────

-- 1. XÓA SẠCH DATABASE CŨ (Reset)
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;

-- 2. TẠO LẠI CÁC BẢNG CHUẨN (CÓ SẴN ROLE, STATUS, KHÔNG BẬT RLS)
CREATE TABLE users (
    id              BIGSERIAL PRIMARY KEY,
    username        VARCHAR(100) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20) DEFAULT 'user',
    status          VARCHAR(20) DEFAULT 'active',
    last_active     TIMESTAMPTZ DEFAULT NOW(),
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE research_reports (
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
    headlines       JSONB DEFAULT '[]',
    created_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE paper_trades (
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

CREATE TABLE admin_config (
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

CREATE TABLE portfolio_snapshots (
    id             BIGSERIAL PRIMARY KEY,
    user_id        BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    balance        DECIMAL(18,4) NOT NULL DEFAULT 0.0,
    total_pnl      DECIMAL(18,4) NOT NULL DEFAULT 0.0,
    snapshot_date  DATE NOT NULL,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, snapshot_date)
);

CREATE TABLE model_accuracy (
    id             BIGSERIAL PRIMARY KEY,
    ticker         VARCHAR(20) NOT NULL,
    model_name     VARCHAR(50),
    forecast_date  DATE,
    predicted_price DECIMAL(18,4),
    actual_price   DECIMAL(18,4),
    error_pct      DECIMAL(6,2),
    created_at     TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE forecast_cache (
    id            BIGSERIAL PRIMARY KEY,
    ticker        VARCHAR(20) NOT NULL,
    days          INT NOT NULL,
    response_json JSONB NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE user_watchlists (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticker     VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, ticker)
);

-- 3. TẠO INDEX ĐỂ TĂNG TỐC ĐỘ ĐỌC DỮ LIỆU
CREATE INDEX idx_research_ticker_time ON research_reports(ticker, created_at DESC);
CREATE INDEX idx_forecast_cache_lookup ON forecast_cache(ticker, days, created_at DESC);
CREATE INDEX idx_user_watchlists_user_id ON user_watchlists(user_id);
CREATE INDEX idx_price_alerts_user_id ON price_alerts(user_id);
CREATE INDEX idx_price_alerts_untriggered ON price_alerts(ticker) WHERE is_triggered = FALSE;

-- 4. BẢNG THÔNG BÁO (NOTIFICATIONS)
CREATE TABLE notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE, -- NULL means global broadcast
    title VARCHAR(255) NOT NULL,
    message TEXT NOT NULL,
    is_read BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- 5. BẢNG CẢNH BÁO GIÁ (PRICE ALERTS)
CREATE TABLE price_alerts (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT REFERENCES users(id) ON DELETE CASCADE,
    ticker VARCHAR(20) NOT NULL,
    condition VARCHAR(10) CHECK (condition IN ('above', 'below')),
    target_price DECIMAL(18,4) NOT NULL,
    is_triggered BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    triggered_at TIMESTAMPTZ
);

-- 5. CẤP LẠI TOÀN BỘ QUYỀN TRUY CẬP (SAU KHI BẢNG ĐÃ TỒN TẠI)
-- (Khắc phục triệt để lỗi đăng ký 500 do backend không có quyền INSERT)
GRANT ALL ON SCHEMA public TO postgres;
GRANT ALL ON SCHEMA public TO public;
GRANT USAGE ON SCHEMA public TO postgres, anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO postgres, anon, authenticated, service_role;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO postgres, anon, authenticated, service_role;

-- 6. TẠO TÀI KHOẢN MẶC ĐỊNH
-- Mật khẩu mặc định: Capmot100123
-- Hash này được tạo dựa trên ADMIN_SECRET_KEY='capmot100123@'
INSERT INTO users (username, password_hash, role, status) 
VALUES 
('admin@forecastai.com', '9e2c6568f62fa2b6775a839ff7d9800dbad9c05ec5a0818955617400a17aa855', 'admin', 'active'),
('user@forecastai.com', '9e2c6568f62fa2b6775a839ff7d9800dbad9c05ec5a0818955617400a17aa855', 'user', 'active')
ON CONFLICT (username) 
DO UPDATE SET 
    password_hash = EXCLUDED.password_hash,
    role = EXCLUDED.role;
