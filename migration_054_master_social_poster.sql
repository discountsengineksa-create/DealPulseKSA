-- migration_054: عمود مستقل لبوستر السوشيال (themed) — منفصل عن logo_url.
-- اللوقو النظيف يبقى في logo_url (يُستعمل في الستوري والكروت)؛ البوستر بالثيم
-- يُستعمل في النشر التلقائي على المنصات (Cloudinary URL transforms من api/social/image_specs.py).
ALTER TABLE master ADD COLUMN IF NOT EXISTS social_poster_url text;
