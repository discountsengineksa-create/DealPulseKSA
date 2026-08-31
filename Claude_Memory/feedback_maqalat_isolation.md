---
name: Maqalat — Zero Reference to DealPulse
description: مشروع Maqalat مستقل تماماً — لا يُذكر dealpulse/discountsengineksa/نبض الصفقات في أي كود أو ملف أو تعليق
type: feedback
originSessionId: a9e30f87-7dcb-4296-950a-248d6bd790d5
---
قاعدة صارمة (2026-08-29): مشروع Maqalat (maqalat.org) لا يحتوي **أي** إشارة إلى:
- `dealpulseksa` / `DealPulse` / `Deal Pulse KSA`
- `discountsengineksa` / `discountsengineksa-create`
- `نبض الصفقات`
- أي API، domain، أو حساب مرتبط بذاك المشروع

**Why:** المستخدم يريد فصلاً تشغيلياً وتحريرياً كاملاً بين المشروعين. أي تسرّب مرجعي (حتى في تعليق داخل الكود، commit message، أو README) يخلق ارتباطاً غير مرغوب فيه — يُضعف الاستقلال البراندي والتشغيلي، ويلوّث Vercel/GitHub/Analytics بربط متبادل.

**How to apply:**
- كل تعليق شرح المصدر لتصميم/فكرة/باترن يوصف بذاته: «Maqalat design system» بدل «DealPulse-inspired»
- الدروس المستفادة من DealPulse تُطبَّق **بلا** ذِكر الأصل
- GitHub org لـMaqalat: `maqalatorg` فقط (ليس discountsengineksa-create)
- الإيميل: `maqalatorg@gmail.com` فقط
- .env variables, package name, metadata — كلها بلا إشارة
- إذا احتجت مرجعاً تاريخياً في memory (للسياق)، فقط في ذاكرة Discounts_Engine، **ليس** داخل ريبو Maqalat
