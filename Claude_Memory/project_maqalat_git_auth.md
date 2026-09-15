---
name: Maqalat Git Auth Trap
description: Windows Git Credential Manager on this laptop is cached for discountsengineksa-create, causing 403 on maqalatorg/maqalat pushes. SOLVED PERMANENTLY 2026-09-15 via a dedicated SSH key + host alias — no more PAT dance.
type: reference
originSessionId: 14a723a5-c3b8-4b2e-9b1e-b55d65dd193f
modified: 2026-09-15T18:27:33.173Z
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

**تحديث 2026-09-15:** هارنس Claude Code يحجب تمرير PAT حقيقي داخل أمر Bash مباشرة (`git push "https://x-access-token:<PAT>@..."`) — classifier يرفضه بسبب "Credential Leakage" حتى لو المالك أعطى التوكن بنفسه بالمحادثة. **الحل المؤقّت (لو احتجته لدفعة واحدة):** أعطِ المالك أمر الـpush الجاهز (بالتوكن كاملاً) ليشغّله هو بتيرمناله الخاص.

**✅ الحل الدائم — طُبِّق 2026-09-15، مُختبَر ويعمل:** SSH key مخصّص لحساب `maqalatorg`، منفصل تماماً عن أي اعتماد HTTPS مخزَّن لحساب `discountsengineksa-create`. لا حاجة لتوكن بعد اليوم على هذا الجهاز.

- المفتاح: `~/.ssh/id_ed25519_maqalat` (+ `.pub`)، بلا passphrase.
- مُضاف لحساب GitHub **maqalatorg** تحت `Settings → SSH and GPG keys` باسم "maqalat-laptop".
- `~/.ssh/config` يحتوي:
  ```
  Host github-maqalat
      HostName github.com
      User git
      IdentityFile ~/.ssh/id_ed25519_maqalat
      IdentitiesOnly yes
  ```
- ريبو `maqalat` المحلي (`C:\Users\PC\Desktop\maqalat`) الـremote عنده مُغيَّر لـ SSH:
  `git remote set-url origin git@github-maqalat:maqalatorg/maqalat.git`
- بعدها `git push origin main` يشتغل مباشرة، بلا أي توكن، بلا سؤال.

**فخّ واجهناه أثناء الإعداد**: توليد مفتاح SSH وكتابة ملفّه محجوبان من الهارنس («Unauthorized Persistence») — لازم المالك يشغّل `ssh-keygen` بنفسه بتيرمناله. أيضاً notepad بويندوز يضيف `.txt` تلقائياً لملف بلا امتداد رغم إن العنوان يظهر بدونها — تحقّق بـ`ls ~/.ssh/` لو SSH يشتكي "Could not resolve hostname"، ورينيمه لو لقيته `config.txt`.

**لو تكرّرت المشكلة بجهاز ثانٍ أو حساب GitHub ثالث مستقبلاً**: نفس الأسلوب — مفتاح SSH مخصّص + host alias في `~/.ssh/config` + `git remote set-url` بالريبو المعني. لا تحاول تعديل Windows Credential Manager المشترك (يؤثر على حساب discountsengineksa-create كمان).
