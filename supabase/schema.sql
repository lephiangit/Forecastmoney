-- ═══════════════════════════════════════════════════════════════════════════════
--  ForecastAI — Supabase schema (phiên bản 2.0, đã siết bảo mật)
-- ═══════════════════════════════════════════════════════════════════════════════
--
--  ⚠️  ĐỌC TRƯỚC KHI CHẠY
--
--  Script này AN TOÀN để chạy trên database đang có dữ liệu: nó dùng
--  CREATE TABLE IF NOT EXISTS và không xoá bảng nào.
--
--  Bản schema cũ mở đầu bằng `DROP SCHEMA public CASCADE` — chạy nhầm nó là mất
--  sạch dữ liệu. Câu lệnh đó đã được bỏ khỏi luồng chính; nếu thực sự cần reset
--  toàn bộ, xem khối được đánh dấu ở cuối file.
--
-- ═══════════════════════════════════════════════════════════════════════════════
--
--  LỖ HỔNG BẢO MẬT ĐƯỢC VÁ Ở BẢN NÀY
--
--  Schema cũ có hai dòng này:
--
--      GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public
--        TO postgres, anon, authenticated, service_role;
--      -- và không bật Row Level Security trên bất kỳ bảng nào
--
--  Vai trò `anon` là vai trò gắn với khoá publishable — khoá này nằm công khai
--  trong `frontend/.env.local` và được gửi tới trình duyệt của mọi người dùng.
--  Nói cách khác: bất kỳ ai mở DevTools cũng lấy được khoá đó, rồi gọi thẳng
--  Supabase REST API để ĐỌC, SỬA và XOÁ toàn bộ bảng — kể cả `users`,
--  `paper_trades`, `admin_config` — mà không cần đi qua backend FastAPI,
--  bỏ qua hoàn toàn lớp xác thực JWT.
--
--  Cách vá gồm hai lớp phòng thủ độc lập:
--
--    Lớp 1 — REVOKE: thu hồi mọi quyền của `anon` và `authenticated` trên bảng.
--    Lớp 2 — RLS:    bật Row Level Security, không tạo policy nào cho hai vai trò
--                    trên, nên mặc định là từ chối tất cả.
--
--  Backend dùng `service_role` key. Vai trò này bỏ qua RLS theo thiết kế của
--  Supabase, nên backend vẫn hoạt động bình thường — với điều kiện:
--
--    ⚠️  SUPABASE_KEY ở backend PHẢI là service_role key (sb_secret_...)
--    ⚠️  Khoá service_role TUYỆT ĐỐI không được xuất hiện ở frontend
--
--  Frontend chỉ dùng khoá anon cho Supabase Auth (đăng nhập Google, gửi email
--  đặt lại mật khẩu). Các API đó không cần quyền trên bảng, nên việc khoá bảng
--  không ảnh hưởng gì tới chức năng đang chạy.
--
-- ═══════════════════════════════════════════════════════════════════════════════


-- ═══════════════════════════════════════════════════════════════════════════════
--  1. BẢNG
-- ═══════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    username        VARCHAR(255) UNIQUE NOT NULL,
    password_hash   VARCHAR(255) NOT NULL,
    role            VARCHAR(20)  DEFAULT 'user'   CHECK (role IN ('user', 'admin')),
    status          VARCHAR(20)  DEFAULT 'active' CHECK (status IN ('active', 'suspended')),
    last_active     TIMESTAMPTZ  DEFAULT NOW(),
    created_at      TIMESTAMPTZ  DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_profiles (
    id          BIGSERIAL PRIMARY KEY,
    user_id     BIGINT UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    name        VARCHAR(100),
    updated_at  TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS research_reports (
    id              BIGSERIAL PRIMARY KEY,
    ticker          VARCHAR(20) NOT NULL,
    sentiment       VARCHAR(20) DEFAULT 'NEUTRAL',
    -- DECIMAL(4,3) chứa được tối đa 9.999 — đủ cho thang [0, 1]
    confidence      DECIMAL(4,3),
    -- sentiment_score có dấu, nằm trong [-1, 1]
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

CREATE TABLE IF NOT EXISTS paper_trades (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT REFERENCES users(id) ON DELETE CASCADE,
    ticker       VARCHAR(20) NOT NULL,
    action       VARCHAR(10) NOT NULL CHECK (action IN ('BUY', 'SELL')),
    quantity     DECIMAL(18,8),
    price        DECIMAL(18,4),
    total_value  DECIMAL(18,4),
    model_signal VARCHAR(30),
    trade_time   TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS admin_config (
    id               BIGSERIAL PRIMARY KEY,
    user_id          BIGINT UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    initial_balance  DECIMAL(18,4) DEFAULT 0.0,
    current_balance  DECIMAL(18,4) DEFAULT 0.0,
    total_pnl        DECIMAL(18,4) DEFAULT 0.0,
    win_trades       INT DEFAULT 0,
    loss_trades      INT DEFAULT 0,
    is_running       BOOLEAN DEFAULT FALSE,
    started_at       TIMESTAMPTZ,
    updated_at       TIMESTAMPTZ DEFAULT NOW()
);

-- Bảng này được database.py dùng nhưng THIẾU trong schema cũ.
CREATE TABLE IF NOT EXISTS bot_configs (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT UNIQUE REFERENCES users(id) ON DELETE CASCADE,
    amount          DECIMAL(18,4) DEFAULT 500,
    end_time        TIMESTAMPTZ,
    assets          JSONB DEFAULT '[]',
    strategy        VARCHAR(20) DEFAULT 'balanced'
                    CHECK (strategy IN ('conservative', 'balanced', 'aggressive')),
    stop_loss       DECIMAL(6,2) DEFAULT 5.0,
    take_profit     DECIMAL(6,2) DEFAULT 15.0,
    min_confidence  DECIMAL(6,2) DEFAULT 70.0,
    updated_at      TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS portfolio_snapshots (
    id             BIGSERIAL PRIMARY KEY,
    user_id        BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    balance        DECIMAL(18,4) NOT NULL DEFAULT 0.0,
    total_pnl      DECIMAL(18,4) NOT NULL DEFAULT 0.0,
    snapshot_date  DATE NOT NULL,
    created_at     TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, snapshot_date)
);

CREATE TABLE IF NOT EXISTS model_accuracy (
    id              BIGSERIAL PRIMARY KEY,
    ticker          VARCHAR(20) NOT NULL,
    model_name      VARCHAR(50),
    forecast_date   DATE,
    predicted_price DECIMAL(18,4),
    actual_price    DECIMAL(18,4),
    error_pct       DECIMAL(8,2),
    created_at      TIMESTAMPTZ DEFAULT NOW(),
    -- Chặn ghi trùng ở tầng database thay vì chỉ kiểm tra trong code:
    -- backend chạy nhiều luồng nền, hai luồng có thể cùng ghi một dự báo.
    UNIQUE (ticker, model_name, forecast_date)
);

CREATE TABLE IF NOT EXISTS forecast_cache (
    id            BIGSERIAL PRIMARY KEY,
    ticker        VARCHAR(20) NOT NULL,
    days          INT NOT NULL,
    response_json JSONB NOT NULL,
    created_at    TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS user_watchlists (
    id         BIGSERIAL PRIMARY KEY,
    user_id    BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticker     VARCHAR(20) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, ticker)
);

CREATE TABLE IF NOT EXISTS notifications (
    id         BIGSERIAL PRIMARY KEY,
    -- NULL = thông báo chung gửi tới toàn bộ người dùng
    user_id    BIGINT REFERENCES users(id) ON DELETE CASCADE,
    title      VARCHAR(255) NOT NULL,
    message    TEXT NOT NULL,
    is_read    BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Trạng thái đọc RIÊNG của từng người với thông báo chung.
-- Thiếu bảng này thì một người bấm "đã đọc" sẽ khiến thông báo biến mất
-- khỏi danh sách của tất cả mọi người.
CREATE TABLE IF NOT EXISTS notification_reads (
    id              BIGSERIAL PRIMARY KEY,
    user_id         BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    notification_id BIGINT NOT NULL REFERENCES notifications(id) ON DELETE CASCADE,
    read_at         TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE (user_id, notification_id)
);

-- Bảng này được database.py và main.py dùng nhưng THIẾU trong schema cũ.
CREATE TABLE IF NOT EXISTS price_alerts (
    id           BIGSERIAL PRIMARY KEY,
    user_id      BIGINT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    ticker       VARCHAR(20) NOT NULL,
    condition    VARCHAR(10) NOT NULL CHECK (condition IN ('above', 'below')),
    target_price DECIMAL(18,4) NOT NULL,
    is_triggered BOOLEAN DEFAULT FALSE,
    triggered_at TIMESTAMPTZ,
    created_at   TIMESTAMPTZ DEFAULT NOW()
);


-- ═══════════════════════════════════════════════════════════════════════════════
--  2. INDEX
-- ═══════════════════════════════════════════════════════════════════════════════
-- Mỗi index dưới đây tương ứng với một câu truy vấn thật trong code.
-- Không tạo index thừa: chúng làm chậm thao tác ghi mà không đem lại lợi ích.

CREATE INDEX IF NOT EXISTS idx_research_ticker_time
    ON research_reports (ticker, created_at DESC);
CREATE INDEX IF NOT EXISTS idx_research_created
    ON research_reports (created_at DESC);

CREATE INDEX IF NOT EXISTS idx_forecast_cache_lookup
    ON forecast_cache (ticker, days, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_watchlists_user
    ON user_watchlists (user_id);

CREATE INDEX IF NOT EXISTS idx_trades_user_time
    ON paper_trades (user_id, trade_time DESC);

CREATE INDEX IF NOT EXISTS idx_snapshots_user_date
    ON portfolio_snapshots (user_id, snapshot_date DESC);

-- Job đánh giá quét đúng các dòng chưa có giá thực tế; index một phần
-- (partial index) chỉ đánh chỉ mục những dòng đó nên rất gọn.
CREATE INDEX IF NOT EXISTS idx_accuracy_pending
    ON model_accuracy (forecast_date)
    WHERE actual_price IS NULL;

CREATE INDEX IF NOT EXISTS idx_accuracy_ticker_model
    ON model_accuracy (ticker, model_name, forecast_date DESC);

CREATE INDEX IF NOT EXISTS idx_notifications_user_time
    ON notifications (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_notification_reads_user
    ON notification_reads (user_id);

-- Vòng lặp kiểm tra cảnh báo giá chỉ quan tâm các cảnh báo chưa kích hoạt.
CREATE INDEX IF NOT EXISTS idx_alerts_active
    ON price_alerts (ticker)
    WHERE is_triggered = FALSE;

CREATE INDEX IF NOT EXISTS idx_alerts_user
    ON price_alerts (user_id, created_at DESC);

-- Bot chỉ quét những user đang bật bot — thường là số ít trong toàn bộ bảng.
CREATE INDEX IF NOT EXISTS idx_admin_config_running
    ON admin_config (user_id)
    WHERE is_running = TRUE;


-- ═══════════════════════════════════════════════════════════════════════════════
--  3. BẢO MẬT — LỚP 1: THU HỒI QUYỀN
-- ═══════════════════════════════════════════════════════════════════════════════
--  Thu hồi mọi quyền trên bảng của `anon` (khoá công khai ở frontend) và
--  `authenticated` (người dùng đã đăng nhập Supabase Auth).
--
--  Riêng quyền USAGE trên schema vẫn giữ, vì Supabase Auth (đăng nhập Google,
--  gửi email đặt lại mật khẩu) cần nó để hoạt động.

REVOKE ALL ON ALL TABLES    IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL SEQUENCES IN SCHEMA public FROM anon, authenticated;
REVOKE ALL ON ALL FUNCTIONS IN SCHEMA public FROM anon, authenticated;

-- Áp dụng cho cả các bảng được tạo sau này, để một bảng mới không vô tình
-- mở lại quyền cho anon.
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES IN SCHEMA public
    REVOKE ALL ON SEQUENCES FROM anon, authenticated;

GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;

-- Backend (service_role) cần toàn quyền để vận hành.
GRANT ALL ON ALL TABLES    IN SCHEMA public TO service_role;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES    TO service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO service_role;


-- ═══════════════════════════════════════════════════════════════════════════════
--  4. BẢO MẬT — LỚP 2: ROW LEVEL SECURITY
-- ═══════════════════════════════════════════════════════════════════════════════
--  Bật RLS mà KHÔNG tạo policy nào cho anon/authenticated → mặc định từ chối
--  mọi thao tác. Đây là lớp phòng thủ thứ hai: kể cả khi ai đó lỡ tay chạy lại
--  một câu GRANT rộng rãi, RLS vẫn chặn.
--
--  service_role bỏ qua RLS theo thiết kế của Supabase, nên backend không bị ảnh hưởng.

ALTER TABLE users                ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_profiles        ENABLE ROW LEVEL SECURITY;
ALTER TABLE research_reports     ENABLE ROW LEVEL SECURITY;
ALTER TABLE paper_trades         ENABLE ROW LEVEL SECURITY;
ALTER TABLE admin_config         ENABLE ROW LEVEL SECURITY;
ALTER TABLE bot_configs          ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolio_snapshots  ENABLE ROW LEVEL SECURITY;
ALTER TABLE model_accuracy       ENABLE ROW LEVEL SECURITY;
ALTER TABLE forecast_cache       ENABLE ROW LEVEL SECURITY;
ALTER TABLE user_watchlists      ENABLE ROW LEVEL SECURITY;
ALTER TABLE notifications        ENABLE ROW LEVEL SECURITY;
ALTER TABLE notification_reads   ENABLE ROW LEVEL SECURITY;
ALTER TABLE price_alerts         ENABLE ROW LEVEL SECURITY;


-- ═══════════════════════════════════════════════════════════════════════════════
--  5. KIỂM CHỨNG
-- ═══════════════════════════════════════════════════════════════════════════════
--  Chạy truy vấn dưới đây sau khi apply. Cột `rls_enabled` phải là `true`
--  ở TẤT CẢ các dòng. Nếu còn dòng nào `false`, bảng đó vẫn đang phơi ra ngoài.

-- SELECT tablename, rowsecurity AS rls_enabled
-- FROM pg_tables
-- WHERE schemaname = 'public'
-- ORDER BY rowsecurity, tablename;

--  Kiểm tra thêm: anon không được còn quyền nào trên bảng.
--  Truy vấn này phải trả về 0 dòng.

-- SELECT grantee, table_name, privilege_type
-- FROM information_schema.role_table_grants
-- WHERE table_schema = 'public' AND grantee IN ('anon', 'authenticated');


-- ═══════════════════════════════════════════════════════════════════════════════
--  6. TÀI KHOẢN QUẢN TRỊ
-- ═══════════════════════════════════════════════════════════════════════════════
--  KHÔNG seed sẵn tài khoản với mật khẩu cố định trong file này.
--
--  Bản schema cũ nhúng thẳng hash của mật khẩu "Capmot100123" cho hai tài khoản
--  admin@forecastai.com và user@forecastai.com, kèm mật khẩu ở dạng chữ thường
--  ngay trong comment. Bất kỳ ai đọc được repo đều đăng nhập được bằng quyền admin.
--
--  Cách làm đúng:
--
--    1. Đăng ký một tài khoản bình thường qua giao diện web (/register).
--
--    2. Nâng tài khoản đó lên quyền admin bằng SQL, thay email cho phù hợp:
--
--         UPDATE users SET role = 'admin' WHERE username = 'email-cua-ban@example.com';
--
--    Hoặc, nếu cần tạo tài khoản trực tiếp trong database, sinh hash bằng:
--
--         python -m backend.routers.auth "MatKhauManhCuaBan"
--
--    rồi:
--
--         INSERT INTO users (username, password_hash, role, status)
--         VALUES ('email-cua-ban@example.com', '<hash vừa sinh>', 'admin', 'active');
--
--  Lưu ý: hash sinh theo định dạng mới có dạng
--  `pbkdf2_sha256$200000$<salt>$<hash>` với salt ngẫu nhiên riêng cho từng
--  tài khoản. Các hash theo định dạng cũ vẫn đăng nhập được và sẽ tự động
--  được nâng cấp ngay sau lần đăng nhập thành công đầu tiên.


-- ═══════════════════════════════════════════════════════════════════════════════
--  7. RESET TOÀN BỘ (NGUY HIỂM — CHỈ DÙNG KHI THỰC SỰ CẦN)
-- ═══════════════════════════════════════════════════════════════════════════════
--  Bỏ comment khối dưới đây sẽ XOÁ SẠCH MỌI DỮ LIỆU. Không có cách hoàn tác.
--  Chỉ dùng khi dựng lại database từ đầu.
--
--  DROP SCHEMA public CASCADE;
--  CREATE SCHEMA public;
--  -- rồi chạy lại toàn bộ file này từ đầu.
