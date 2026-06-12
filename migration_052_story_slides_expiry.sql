-- migration_052: مدة عرض الشريحة — expires_at (NULL = دائم).
-- العرض في الموقع/الميني يستبعد المنتهية؛ الداشبورد يعرض الحالة ويسمح بالحذف اليدوي.
ALTER TABLE story_slides ADD COLUMN IF NOT EXISTS expires_at timestamptz;
