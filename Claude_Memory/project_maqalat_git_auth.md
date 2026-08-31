---
name: Maqalat Git Auth Trap
description: Windows Git Credential Manager on this laptop is cached for discountsengineksa-create — pushes to maqalatorg/maqalat repo fail 403. Workaround uses fine-grained PAT inline in URL.
type: reference
originSessionId: 14a723a5-c3b8-4b2e-9b1e-b55d65dd193f
---
**الفخّ:** Windows Credential Manager كاش git creds للحساب `discountsengineksa-create` (DealPulse). أي `git push origin main` لأي ريبو تحت `maqalatorg` يفشل بـ:
```
remote: Permission to maqalatorg/maqalat.git denied to discountsengineksa-create.
fatal: unable to access 'https://github.com/maqalatorg/maqalat.git/': 403
```

**الحل السريع (بدون حفظ التوكن على القرص):**
1. يوصل المستخدم PAT من حساب `maqalatorg` (fine-grained، repo محدّد، Contents R/W).
2. push مباشر بتوكن inline:
   ```bash
   git push "https://x-access-token:<PAT>@github.com/maqalatorg/maqalat.git" main
   ```
3. لا تُحدّث `origin` URL بالتوكن (يُحفظ في `.git/config`) — استخدم URL inline فقط لدفعة واحدة.

**الحلول الدائمة (لم تُطبَّق بعد — لو صار push متكرر):**
- تثبيت `gh` CLI + `gh auth switch` بين الحسابين (يتطلب تسجيل الاثنين).
- Windows Credential Manager → مسح `git:https://github.com` القديم → git يسأل تفاعلياً عن جديد.
- إضافة SSH key لـ`maqalatorg` وتحويل remote لـSSH.

**Why:** المستخدم يدير جهاز واحد لريبوهين تحت حسابين GitHub مختلفين. الجهاز افتراضياً مسجّل بحساب DealPulse لأنه الأقدم.

**How to apply:** أي push فاشل لريبو `maqalatorg/*` بخطأ 403 «denied to discountsengineksa-create» → اطلب PAT جديد من المستخدم (لا تحاول الـSSH/CM بلا سؤال). PAT fine-grained (repo محدّد، Contents R/W، 90-day expiry) هو الأسرع.

**تنظيف:** بعد الـpush، ذكّر المستخدم بإلغاء التوكن من `github.com/settings/personal-access-tokens` — لأنه صار في تاريخ المحادثة.
