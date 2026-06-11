-- migration_051: تحويل 25 عمود timestamp without time zone -> timestamptz
-- USING col AT TIME ZONE UTC: يوسم القيم الـ naive (المخزّنة UTC) كلحظات UTC دقيقة.
-- عكسي: ALTER ... TYPE timestamp USING col AT TIME ZONE UTC;

BEGIN;
ALTER TABLE "action_logs" ALTER COLUMN "action_time" TYPE timestamptz USING "action_time" AT TIME ZONE 'UTC';
ALTER TABLE "auto_rules" ALTER COLUMN "last_run" TYPE timestamptz USING "last_run" AT TIME ZONE 'UTC';
ALTER TABLE "bot_users" ALTER COLUMN "joined_at" TYPE timestamptz USING "joined_at" AT TIME ZONE 'UTC';
ALTER TABLE "bot_users" ALTER COLUMN "last_seen" TYPE timestamptz USING "last_seen" AT TIME ZONE 'UTC';
ALTER TABLE "bot_users" ALTER COLUMN "search_date_timestamp" TYPE timestamptz USING "search_date_timestamp" AT TIME ZONE 'UTC';
ALTER TABLE "broadcast_logs" ALTER COLUMN "sent_at" TYPE timestamptz USING "sent_at" AT TIME ZONE 'UTC';
ALTER TABLE "code_reports" ALTER COLUMN "created_at" TYPE timestamptz USING "created_at" AT TIME ZONE 'UTC';
ALTER TABLE "code_reports" ALTER COLUMN "resolved_at" TYPE timestamptz USING "resolved_at" AT TIME ZONE 'UTC';
ALTER TABLE "content_studio_logs" ALTER COLUMN "created_at" TYPE timestamptz USING "created_at" AT TIME ZONE 'UTC';
ALTER TABLE "direct_search" ALTER COLUMN "search_date" TYPE timestamptz USING "search_date" AT TIME ZONE 'UTC';
ALTER TABLE "master" ALTER COLUMN "suspended_at" TYPE timestamptz USING "suspended_at" AT TIME ZONE 'UTC';
ALTER TABLE "password_reset_tokens" ALTER COLUMN "created_at" TYPE timestamptz USING "created_at" AT TIME ZONE 'UTC';
ALTER TABLE "password_reset_tokens" ALTER COLUMN "expires_at" TYPE timestamptz USING "expires_at" AT TIME ZONE 'UTC';
ALTER TABLE "product_comparisons" ALTER COLUMN "created_at" TYPE timestamptz USING "created_at" AT TIME ZONE 'UTC';
ALTER TABLE "security_blacklist" ALTER COLUMN "block_date" TYPE timestamptz USING "block_date" AT TIME ZONE 'UTC';
ALTER TABLE "security_threats" ALTER COLUMN "detection_time" TYPE timestamptz USING "detection_time" AT TIME ZONE 'UTC';
ALTER TABLE "sent_coupon_messages" ALTER COLUMN "sent_at" TYPE timestamptz USING "sent_at" AT TIME ZONE 'UTC';
ALTER TABLE "social_posts_log" ALTER COLUMN "attempted_at" TYPE timestamptz USING "attempted_at" AT TIME ZONE 'UTC';
ALTER TABLE "social_posts_log" ALTER COLUMN "completed_at" TYPE timestamptz USING "completed_at" AT TIME ZONE 'UTC';
ALTER TABLE "story_views" ALTER COLUMN "viewed_at" TYPE timestamptz USING "viewed_at" AT TIME ZONE 'UTC';
ALTER TABLE "support_tickets" ALTER COLUMN "created_at" TYPE timestamptz USING "created_at" AT TIME ZONE 'UTC';
ALTER TABLE "support_tickets" ALTER COLUMN "replied_at" TYPE timestamptz USING "replied_at" AT TIME ZONE 'UTC';
ALTER TABLE "unavailable_codes_requests" ALTER COLUMN "requested_at" TYPE timestamptz USING "requested_at" AT TIME ZONE 'UTC';
ALTER TABLE "web_users" ALTER COLUMN "created_at" TYPE timestamptz USING "created_at" AT TIME ZONE 'UTC';
ALTER TABLE "web_users" ALTER COLUMN "last_seen" TYPE timestamptz USING "last_seen" AT TIME ZONE 'UTC';
COMMIT;
