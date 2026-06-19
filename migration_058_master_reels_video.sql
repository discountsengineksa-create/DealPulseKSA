-- migration_058: عمود رابط فيديو Reels لكل متجر.
-- Instagram Reels تتطلّب MP4 حقيقي (≥3s، ≤90s، ≥720p). البوستر الثابت لا يصلح.
-- ثلاثة مسارات تملأ هذا العمود:
--   (1) المالك يرفع MP4 يدوياً عبر الستوديو في الداشبورد — أعلى جودة، عمل لمرة
--   (2) مولّد تلقائي يبني فيديو Ken Burns من البوستر (يتطلّب imageio-ffmpeg)
--   (3) Cloudinary video transform — مدعوم على معظم الخطط، جودة محدودة
-- لو العمود NULL → dispatcher يتخطّى Reel لهذا المتجر (Feed + Story يستمران).
ALTER TABLE master ADD COLUMN IF NOT EXISTS reels_video_url text;
