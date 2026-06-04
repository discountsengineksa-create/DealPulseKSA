-- ════════════════════════════════════════════════════════════════════════════
-- Migration 030: trend_overrides — تحكّم يدوي بمراكز الترند (admin pinning)
-- ════════════════════════════════════════════════════════════════════════════
-- المالك يبي يتحكم بأي متجر يظهر في أي مركز (يومي/أسبوعي)، والباقي يتزحّح
-- تلقائياً حسب الخوارزمية. مثال: لو ثبّت "نمشي 3" في المركز الثاني للأسبوعي،
-- يصير المتجر اللي كان أصلاً في المركز الثاني → المركز الثالث، والثالث الرابع.
--
-- ملاحظة: نستخدم "window_kind" بدل "window" لأن WINDOW كلمة محجوزة (window
-- functions) في PostgreSQL وتسبب syntax errors.
--
-- التطبيق:
--   python api/run_migration.py migration_030_trend_overrides.sql
-- ════════════════════════════════════════════════════════════════════════════

CREATE TABLE IF NOT EXISTS trend_overrides (
    id           BIGSERIAL    PRIMARY KEY,
    window_kind  TEXT         NOT NULL CHECK (window_kind IN ('daily', 'weekly')),
    rank         INTEGER      NOT NULL CHECK (rank >= 1 AND rank <= 10),
    store_id     TEXT         NOT NULL,
    set_at       TIMESTAMPTZ  DEFAULT NOW(),
    set_by       TEXT,
    CONSTRAINT trend_overrides_uniq_rank  UNIQUE (window_kind, rank),
    CONSTRAINT trend_overrides_uniq_store UNIQUE (window_kind, store_id)
);

COMMENT ON TABLE  trend_overrides              IS 'تجاوزات يدوية لمراكز الترند — تطغى على نتائج الخوارزمية في /api/v1/trend/*.';
COMMENT ON COLUMN trend_overrides.window_kind  IS 'النافذة: daily (3 مراكز) أو weekly (7 مراكز).';
COMMENT ON COLUMN trend_overrides.rank         IS 'المركز المثبّت (1 = الأعلى طلباً، 2 = الأكثر شعبية، …).';
COMMENT ON COLUMN trend_overrides.store_id     IS 'معرّف المتجر (master.store_id) — بدون FK لأن store_id غير فريد في master.';
COMMENT ON COLUMN trend_overrides.set_by       IS 'هوية الأدمن الذي ثبّت المركز (للسجل — اختياري).';

CREATE INDEX IF NOT EXISTS trend_overrides_window_idx ON trend_overrides (window_kind);

-- ─── ✅ تحقّق سريع ─────────────────────────────────────────────────────────
-- SELECT window_kind, rank, store_id, set_at FROM trend_overrides ORDER BY window_kind, rank;
