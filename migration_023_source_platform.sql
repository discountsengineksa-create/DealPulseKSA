-- Migration 023: master.source_platform
-- Run once: psql -U postgres -d discounts_engine -f migration_023_source_platform.sql
--
-- لماذا: كود الإضافة (إدخال الماستر) والتعديل وجدول الكوبونات يستخدمون عمود
-- source_platform، لكنه لم يكن موجوداً في الجدول — فكانت كل عملية إضافة متجر
-- تفشل بـ «column "source_platform" does not exist» وكان جدول الكوبونات يتعطّل.

ALTER TABLE master
    ADD COLUMN IF NOT EXISTS source_platform TEXT;

COMMENT ON COLUMN master.source_platform IS
    'مصدر/منصة المتجر («من أين») — حقل نصّي حرّ يُدار من الداشبورد عند إضافة/تعديل المتجر.';
