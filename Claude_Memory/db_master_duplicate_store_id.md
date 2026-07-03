---
name: master.store_id Not Unique — Duplicate "نون"
description: master.store_id has a duplicate (نون, ids 8 and 21) blocking UNIQUE constraint and FK references
type: project
originSessionId: b489c3e5-2f5b-4bb5-8cde-153cfa943309
---
جدول `master` فيه صفّان لمتجر `نون` (id=8 و id=21) — اكتشفناه أثناء migration 029.

**Why:** تكرار قديم في البيانات. منع إضافة `UNIQUE` على `master.store_id` ومنع إضافة `FOREIGN KEY ... REFERENCES master(store_id)` على الجداول الجديدة (`code_reports`, `story_views`). الـ migration 029 أُطلِقت بدون FKs نتيجة لهذا — التطبيق يتحقّق من وجود `store_id` قبل INSERT (`api/utils/code_reports.py`).

**How to apply:**
- قبل أي migration تحاول `UNIQUE(store_id)` أو `FK -> master(store_id)`: تحقّق أولاً، وسوّي dedupe migration مستقلة (دمج counters/clicks للصفّين ثم حذف أحدهما).
- لو سويت dedupe وأضفت UNIQUE: عد لـ `migration_029_reports_and_stories.sql` وأضف الـ FKs المحذوفة في migration جديدة (`ALTER TABLE code_reports ADD CONSTRAINT ... FK ...`).
- للتحقّق السريع:
  ```sql
  SELECT store_id, COUNT(*), array_agg(id) FROM master GROUP BY store_id HAVING COUNT(*) > 1;
  ```
