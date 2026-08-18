/**
 * نبض الصفقات — عرض الاجتماع الأول (عربي · RTL)
 *
 * المولّد هو المصدر، لا ملف الـPPTX. أي تعديل هنا ثم:
 *     node outreach/company_profile/deck/build_deck.js
 *
 * الهوية: أرضية #141C31 (حبر العلامة) وأخضر #10B981 — نفس سلّم دليل الهوية
 * الداكن، وكل زوج نصّ/أرضية فيه مقيس بـWCAG (انظر README في نفس المجلّد).
 *
 * ⚠️ الخطّ Arial لا IBM Plex Sans Arabic: الخطّ لا يُضمَّن في PPTX، فلو لم يكن
 * مثبّتاً على جهاز العارض سقط لبديل عشوائي وانكسر التخطيط أمام المعلن. Arial
 * موجود على كل ويندوز وماك ويشكّل العربية صحيحاً. لو ثبّتّ IBM Plex Sans Arabic
 * على جهازك، بدّل ثابت FONT أدناه وحده.
 */
const path = require("path");
const fs = require("fs");
const pptxgen = require("pptxgenjs");

const HERE = __dirname;
const OUT = path.join(HERE, "DealPulse_Deck_AR.pptx");
const LOGO = path.join(HERE, "..", "logo_on_dark.png");

const FONT = "Arial";

// سلّم الداكن — القيم نفسها التي في profile_dark.css وguidelines.css
const BG = "141C31";       // الأرضية = حبر العلامة
const DEEP = "0B1120";     // أعمق — للأشرطة والبطاقة المميّزة
const SURF = "1B2440";     // سطح مرتفع
const LINE = "2C3A55";     // حدّ شعري
const TEXT = "E3E8EF";     // متن — 13.75:1
const DIM = "C3CBDA";      // ثانوي — 10.38:1
const MUTE = "9AA6BC";     // حواشٍ — 6.90:1
const ACC = "10B981";      // الأخضر الحامل على الداكن — 6.68:1
const ONACC = "04231A";    // نصّ فوق لوح أخضر — 6.57:1
const ONACC2 = "053B2C";   // ثانوي فوق لوح أخضر — 4.96:1
const DANGER = "FDA29B";   // الأحمر الوظيفي، نسخته الفاتحة للداكن

const W = 13.333, H = 7.5;
const M = 0.75;                       // هامش جانبي — أكبر من 0.5" المطلوب
const CW = W - M * 2;                 // عرض المحتوى

const pres = new pptxgen();
pres.layout = "LAYOUT_WIDE";          // يُضبط قبل أي شريحة
pres.rtlMode = true;
pres.author = "Deal Pulse KSA";
pres.company = "نبض الصفقات";
pres.title = "نبض الصفقات — عرض تعريفي";

// ── لبنات مشتركة ────────────────────────────────────────────────────────
/** نصّ عربي: محاذاة يمين وRTL افتراضاً. */
const ar = (o) => Object.assign({ fontFace: FONT, align: "right", rtlMode: true }, o);

function slide(sectionLabel) {
  const s = pres.addSlide();
  s.background = { color: BG };
  if (sectionLabel) {
    s.addText("نبض الصفقات", ar({
      x: W - M - 3, y: 0.34, w: 3, h: 0.3,
      fontSize: 11, bold: true, color: "FFFFFF",
    }));
    s.addText(sectionLabel, Object.assign(ar({}), {
      x: M, y: 0.34, w: 4.5, h: 0.3,
      fontSize: 11, color: MUTE, align: "left",
    }));
  }
  return s;
}

/** عنوان الشريحة + سطر تمهيدي اختياري. بلا خطّ زخرفي تحته. */
function heading(s, title, lead, opts = {}) {
  const y = opts.y == null ? 0.95 : opts.y;
  s.addText(title, ar({
    x: M, y, w: CW, h: opts.th || 0.75,
    fontSize: opts.size || 34, bold: true, color: "FFFFFF", margin: 0,
  }));
  if (lead) {
    s.addText(lead, ar({
      x: M, y: y + (opts.th || 0.75) + 0.06, w: opts.lw || CW, h: opts.lh || 0.62,
      fontSize: 14.5, color: DIM, lineSpacingMultiple: 1.35, margin: 0,
    }));
  }
}

/** بطاقة: سطح مرتفع بحدّ شعري. تُميَّز بحدّ أخضر لا بخلفية فاتحة (الأرضية داكنة). */
function card(s, { x, y, w, h, accent = false, deep = false }) {
  s.addShape(pres.ShapeType.roundRect, {
    x, y, w, h, rectRadius: 0.11,
    fill: { color: deep ? DEEP : SURF },
    line: { color: accent ? ACC : LINE, width: accent ? 1.25 : 0.75 },
  });
}

/** قرص أخضر يحمل رقماً أو حرفاً — الموتيف المتكرّر في العرض كلّه. */
function disc(s, { x, y, d = 0.46, label, color = ACC, txt = ONACC, size = 13 }) {
  s.addShape(pres.ShapeType.ellipse, { x, y, w: d, h: d, fill: { color } });
  s.addText(String(label), {
    x, y, w: d, h: d, fontFace: FONT, fontSize: size, bold: true,
    color: txt, align: "center", valign: "middle", margin: 0,
  });
}

function cardText(s, { x, y, w, title, body, titleSize = 15, bodySize = 12, bodyH = 0.78 }) {
  s.addText(title, ar({ x, y, w, h: 0.34, fontSize: titleSize, bold: true,
    color: "FFFFFF", margin: 0 }));
  if (body) {
    s.addText(body, ar({ x, y: y + 0.36, w, h: bodyH, fontSize: bodySize,
      color: DIM, lineSpacingMultiple: 1.3, margin: 0 }));
  }
}

function foot(s, n) {
  s.addText(String(n), {
    x: M, y: H - 0.55, w: 1, h: 0.3, fontFace: FONT, fontSize: 10,
    color: MUTE, align: "left", margin: 0,
  });
}

// ═══ 1 · الغلاف ══════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: BG };
  s.addImage({ path: LOGO, x: (W - 4.6) / 2, y: 1.05, w: 4.6, h: 4.6 / 1.551 });
  s.addText("نضع علامتك أمام المشتري السعودي في لحظة القرار", ar({
    x: 1.4, y: 4.15, w: W - 2.8, h: 0.7, fontSize: 27, bold: true,
    color: "FFFFFF", align: "center", margin: 0,
  }));
  s.addText("منصّة سعودية للعروض والمحتوى الشرائي", ar({
    x: 1.4, y: 4.92, w: W - 2.8, h: 0.4, fontSize: 15, color: ACC,
    align: "center", margin: 0,
  }));
  s.addShape(pres.ShapeType.rect, { x: 0, y: H - 0.95, w: W, h: 0.95,
    fill: { color: DEEP } });
  const contacts = [
    ["الموقع", "dealpulseksa.com"],
    ["البريد", "dealpulseksa@gmail.com"],
    ["واتساب", "0534448900"],
  ];
  contacts.forEach(([k, v], i) => {
    const x = M + i * ((CW) / 3);
    s.addText(k, { x, y: H - 0.78, w: CW / 3 - 0.3, h: 0.24, fontFace: FONT,
      fontSize: 9.5, bold: true, color: ACC, align: "left", margin: 0, rtlMode: true });
    s.addText(v, { x, y: H - 0.53, w: CW / 3 - 0.3, h: 0.3, fontFace: FONT,
      fontSize: 12.5, color: "FFFFFF", align: "left", margin: 0 });
  });
  s.addNotes("افتح بسؤال لا بتعريف: «كم طلب يخرج من صفحة الدفع عندكم يدوّر كود ولا يرجع؟» — ثم انتقل للشريحة الثانية.");
}

// ═══ 2 · الفكرة في سطر ═══════════════════════════════════════════════════
{
  const s = slide("الفكرة");
  s.addText("ما نبيعه شيء واحد:", ar({
    x: M, y: 2.15, w: CW, h: 0.55, fontSize: 22, color: DIM, align: "center", margin: 0,
  }));
  s.addText("نيّة شراء جاهزة", ar({
    x: M, y: 2.75, w: CW, h: 1.15, fontSize: 54, bold: true, color: ACC,
    align: "center", margin: 0,
  }));
  s.addText(
    "من يبحث عن كود خصم يكون قد اختار منتجه فعلاً — ولم يبقَ إلا أن يُتمّ طلبه.\n" +
    "وهذا أقصر طريق بين المحتوى والمبيعة، وأقلّه هدراً في الإنفاق.", ar({
    x: 2.2, y: 4.05, w: W - 4.4, h: 1.1, fontSize: 16, color: TEXT,
    align: "center", lineSpacingMultiple: 1.45, margin: 0,
  }));
  foot(s, 2);
  s.addNotes("لا تشرح المنصّة بعد. ثبّت هذه الجملة أولاً — كل ما بعدها خدمة لها.");
}

// ═══ 3 · المشكلة ═════════════════════════════════════════════════════════
{
  const s = slide("أين تُفقد الطلبات");
  heading(s, "خانة «كود الخصم» تُخرج مشتريك من متجرك",
    "المشتري يصل إلى الدفع — ومعه مدى أو محفظة أو تقسيط — فيرى الخانة فارغة أمامه، فيخرج يبحث عمّا يملأها به.\nوهذا يحدث اليوم بلا علاقة بنا. السؤال الوحيد: ماذا يجد في تلك الدقيقة؟",
    { lh: 0.95 });

  // خانة الكود الفارغة — العنصر الذي يحمل الفكرة كلّها
  s.addShape(pres.ShapeType.roundRect, {
    x: (W - 6.2) / 2, y: 3.05, w: 6.2, h: 0.72, rectRadius: 0.08,
    fill: { color: SURF }, line: { color: DANGER, width: 1.25, dashType: "dash" },
  });
  s.addText("كود الخصم", ar({
    x: (W - 6.2) / 2 + 0.25, y: 3.05, w: 5.7, h: 0.72, fontSize: 15,
    color: MUTE, valign: "middle", margin: 0,
  }));
  s.addText("خانة فارغة  =  احتمالية عدم الشراء عالية", ar({
    x: M, y: 3.85, w: CW, h: 0.4, fontSize: 15, bold: true, color: DANGER,
    align: "center", margin: 0,
  }));

  const outs = [
    ["يجد كودكم", "يعود ويُتمّ الطلب", ACC],
    ["يجد كود منافس", "يشتري من غيركم", DANGER],
    ["لا يجد شيئاً", "تبقى السلة معلّقة", MUTE],
  ];
  const cw = (CW - 0.9) / 3;
  outs.forEach(([t, b, col], i) => {
    const x = M + i * (cw + 0.45);
    card(s, { x, y: 4.6, w: cw, h: 1.5, accent: col === ACC });
    s.addText(t, ar({ x: x + 0.3, y: 4.82, w: cw - 0.6, h: 0.36,
      fontSize: 16, bold: true, color: col, margin: 0 }));
    s.addText(b, ar({ x: x + 0.3, y: 5.24, w: cw - 0.6, h: 0.6,
      fontSize: 13, color: DIM, margin: 0 }));
  });
  foot(s, 3);
  s.addNotes("النقطة: السلّة المعلّقة أثمن من المتروكة — صاحبها قرّر الشراء وينتظر سبباً واحداً. نحن نوفّر السبب.");
}

// ═══ 4 · الدورة ══════════════════════════════════════════════════════════
{
  const s = slide("موقعنا في رحلة المشتري");
  heading(s, "أين نقف بالضبط", null, { th: 0.6 });

  const oval = (x, y, w, h, label, fill, txt, ln) => {
    s.addShape(pres.ShapeType.ellipse, { x, y, w, h,
      fill: { color: fill }, line: ln ? { color: ln, width: 1.25 } : undefined });
    s.addText(label, { x, y, w, h, fontFace: FONT, fontSize: 15, bold: true,
      color: txt, align: "center", valign: "middle", margin: 0, rtlMode: true });
  };
  // RTL: المشتري يميناً، المتجر يساراً — نفس ترتيب النسخة العربية من الملف
  oval(5.35, 1.75, 2.65, 0.95, "نبض الصفقات", ACC, ONACC, null);
  oval(9.55, 4.35, 2.75, 0.95, "المشتري", SURF, TEXT, LINE);
  oval(1.0, 4.35, 2.75, 0.95, "متجرك", DEEP, "FFFFFF", ACC);

  const arrow = (x1, y1, x2, y2, color) => s.addShape(pres.ShapeType.line, {
    x: Math.min(x1, x2), y: Math.min(y1, y2),
    w: Math.abs(x2 - x1), h: Math.abs(y2 - y1),
    line: { color, width: 1.75, endArrowType: "triangle" },
    flipH: x2 < x1, flipV: y2 < y1,
  });
  arrow(9.45, 4.83, 3.9, 4.83, MUTE);           // 1 المشتري ← متجرك
  arrow(10.0, 4.3, 8.15, 2.75, MUTE);           // 2 المشتري ← نبض
  arrow(5.3, 2.75, 3.5, 4.3, ACC);              // 3+4 نبض ← متجرك

  disc(s, { x: 6.55, y: 5.02, label: "1" });
  s.addText("يدخل ويعبّئ السلة", ar({ x: 5.35, y: 5.55, w: 2.65, h: 0.3,
    fontSize: 12.5, color: DIM, align: "center", margin: 0 }));

  disc(s, { x: 9.05, y: 3.35, label: "2" });
  s.addText("يخرج يبحث عن كود", ar({ x: 8.6, y: 3.9, w: 2.6, h: 0.3,
    fontSize: 12.5, color: DIM, align: "center", margin: 0 }));

  disc(s, { x: 3.62, y: 3.3, label: "3" });
  s.addText("يأخذ كودك عندنا", ar({ x: 1.25, y: 2.95, w: 2.2, h: 0.3,
    fontSize: 12.5, bold: true, color: ACC, align: "center", margin: 0 }));
  s.addText("= نيّة شراء مؤكّدة", ar({ x: 1.25, y: 3.28, w: 2.2, h: 0.3,
    fontSize: 12, color: ACC, align: "center", margin: 0 }));

  disc(s, { x: 2.05, y: 5.5, label: "4" });
  s.addText("يعود ويُتمّ الطلب", ar({ x: 2.6, y: 5.53, w: 2.4, h: 0.3,
    fontSize: 12.5, bold: true, color: ACC, align: "left", margin: 0 }));

  s.addShape(pres.ShapeType.roundRect, { x: M, y: 6.35, w: CW, h: 0.62,
    rectRadius: 0.09, fill: { color: SURF }, line: { color: LINE, width: 0.75 } });
  s.addText("وبدوننا تنكسر الدورة عند الخطوة 2: يخرج يبحث فلا يجد كودك — فإمّا يجد كود منافسك، أو لا يجد شيئاً فتبقى السلة معلّقة.",
    ar({ x: M + 0.3, y: 6.35, w: CW - 0.6, h: 0.62, fontSize: 12.5,
      color: DIM, valign: "middle", margin: 0 }));
  foot(s, 4);
  s.addNotes("هذا الرسم من سبورة المالك. لا تشرحه سطراً سطراً — أشر إلى الخطوة 2 وقل: هنا نقف، وهنا يُحسم الطلب.");
}

// ═══ 5 · أربع قنوات ══════════════════════════════════════════════════════
{
  const s = slide("كيف نصل إليه");
  heading(s, "أربع قنوات على جمهور واحد",
    "لسنا موقعاً واحداً. العرض يصل إلى المتسوّق من حيث هو، ويعود به إلى صفحة علامتك.");

  const ch = [
    ["الموقع والمحتوى", "صفحة دائمة لكل علامة، ومكتبة أدلّة شرائية عربية، وصفحات مواسم"],
    ["بوت تيليجرام", "وصول مباشر: بحث وعرض فوري وتنبيهات — بلا تحميل تطبيق ولا تسجيل"],
    ["التطبيق المصغّر", "واجهة تصفّح كاملة داخل تيليجرام، بنفس المصدر وبنفس لحظة التحديث"],
    ["حسابات التواصل", "حضور بصري يحمل العرض إلى جمهور لا يصل عبر البحث"],
  ];
  const cw = (CW - 0.5) / 2, chh = 1.5;
  ch.forEach(([t, b], i) => {
    const col = i % 2, row = (i / 2) | 0;
    const x = M + col * (cw + 0.5), y = 2.85 + row * (chh + 0.42);
    card(s, { x, y, w: cw, h: chh });
    disc(s, { x: x + cw - 0.75, y: y + 0.28, d: 0.42, label: i + 1, size: 12 });
    cardText(s, { x: x + 0.35, y: y + 0.28, w: cw - 1.3, title: t, body: b });
  });
  foot(s, 5);
  s.addNotes("أربع لا ثلاث — حسابات التواصل قناة قائمة بذاتها، لا امتداد للموقع.");
}

// ═══ 6 · الخدمات ═════════════════════════════════════════════════════════
{
  const s = slide("ماذا نصنع لعلامتك");
  heading(s, "سبع خدمات، مخرَج ملموس لكلٍّ منها", null, { th: 0.6 });

  const sv = [
    ["صفحة علامة دائمة", "أكثر من عرض وأكثر من كود في وقت واحد — أصل يعمل بعد انتهاء الحملة"],
    ["مقارنات وأدلّة شرائية", "الصيغ التي يقرأها المشتري في الخطوة الأخيرة، ويقتبسها المساعد الذكي"],
    ["تهيئة الظهور في البحث", "بمفردات السوق لا بالفصحى، مع بيانات منظّمة وربط داخلي ومتابعة فهرسة"],
    ["صفحات المواسم", "رمضان والعيدان ويوم التأسيس والوطني والجمعة البيضاء — بتقويم يتتبّع الهجري"],
    ["التوزيع على قنواتنا", "الموقع والبوت والتطبيق المصغّر والتواصل، مع إبراز في الواجهة"],
    ["ستوري العلامة", "مساحة بصرية أعلى الواجهة — حضور متجدّد لا مرّة واحدة"],
    ["الترند اليومي والأسبوعي", "مكانه محدود، فيصير بين العلامات سباق عليه"],
    ["والتركيب حسب هدفك", "كل خدمة قائمة بذاتها، ولا باقة ثابتة تُفرض عليك"],
  ];
  const cw = (CW - 0.8) / 3, chh = 1.32;
  sv.forEach(([t, b], i) => {
    const col = i % 3, row = (i / 3) | 0;
    const x = M + col * (cw + 0.4), y = 2.05 + row * (chh + 0.36);
    const last = i === sv.length - 1;
    card(s, { x, y, w: cw, h: chh, accent: last });
    s.addText(t, ar({ x: x + 0.3, y: y + 0.22, w: cw - 0.6, h: 0.32,
      fontSize: 13.5, bold: true, color: last ? ACC : "FFFFFF", margin: 0 }));
    s.addText(b, ar({ x: x + 0.3, y: y + 0.56, w: cw - 0.6, h: 0.66,
      fontSize: 11, color: DIM, lineSpacingMultiple: 1.25, margin: 0 }));
  });
  foot(s, 6);
  s.addNotes("لا تقرأها كلّها. اذكر ثلاثاً تناسبهم واترك الباقي للملف التعريفي.");
}

// ═══ 7 · الشبكة في الخلفية ═══════════════════════════════════════════════
{
  const s = slide("ما يُبنى لك بعد الاتفاق");
  heading(s, "لا نضيف اسمك إلى قائمة — نبني حولك شبكة",
    "ثلاثة مصادر تلتقط الباحث، وصفحات مترابطة تمرّر قوّتها إلى صفحتك، وصفحتك تقوده إلى متجرك.",
    { th: 0.62, lh: 0.5 });

  const row = (y, items, opt = {}) => {
    const n = items.length, gap = 0.4;
    const cw = (CW - gap * (n - 1)) / n;
    items.forEach(([t, b], i) => {
      const x = M + i * (cw + gap);
      card(s, { x, y, w: cw, h: opt.h || 0.95, accent: opt.accent, deep: opt.deep });
      s.addText(t, ar({ x: x + 0.2, y: y + 0.13, w: cw - 0.4, h: 0.3,
        fontSize: 12.5, bold: true, color: opt.tcolor || "FFFFFF",
        align: "center", margin: 0 }));
      if (b) s.addText(b, ar({ x: x + 0.2, y: y + 0.44, w: cw - 0.4, h: 0.42,
        fontSize: 10.5, color: opt.bcolor || MUTE, align: "center", margin: 0 }));
    });
  };
  const chevron = (y) => s.addShape(pres.ShapeType.triangle, {
    x: W / 2 - 0.16, y, w: 0.32, h: 0.2, fill: { color: ACC }, rotate: 180 });

  row(2.35, [["بحث جوجل", "نيّة شرائية مباشرة"],
             ["مساعدات الذكاء الاصطناعي", "اقتباس داخل الإجابة"],
             ["تيليجرام والتواصل", "وصول مباشر لجمهورنا"]], { deep: true });
  chevron(3.42);
  row(3.72, [["عنقود المقارنات والأدلّة", "مقالات يلتقط كلٌّ منها بحثاً"],
             ["صفحة الموسم", "بوابة ترتفع مع ذروة الطلب"],
             ["محاور الفئات والمتاجر", "صفحات تجميعية تمرّر قوّتها"]], {});
  s.addText("ربط داخلي متبادل بين هذه الصفحات — فتتراكم قوّتها بدل أن تتبعثر", ar({
    x: M, y: 4.72, w: CW, h: 0.3, fontSize: 11.5, bold: true, color: ACC,
    align: "center", margin: 0 }));
  chevron(5.06);

  card(s, { x: M, y: 5.36, w: CW, h: 0.72, accent: true });
  s.addText("صفحة علامتك — الوجهة الثابتة: عرضك وتعريفك وهويتك، برابط دائم وبيانات منظّمة",
    ar({ x: M + 0.3, y: 5.36, w: CW - 0.6, h: 0.72, fontSize: 13, bold: true,
      color: ACC, align: "center", valign: "middle", margin: 0 }));
  chevron(6.14);
  card(s, { x: M, y: 6.42, w: CW, h: 0.58, deep: true });
  s.addText("متجرك — المشتري يصل ومعه الكود، والطلب يكتمل", ar({
    x: M + 0.3, y: 6.42, w: CW - 0.6, h: 0.58, fontSize: 12.5, bold: true,
    color: "FFFFFF", align: "center", valign: "middle", margin: 0 }));
  foot(s, 7);
  s.addNotes("هذي الشريحة تفصلنا عن مواقع الكوبونات: هم يضيفون سطراً في قائمة، ونحن نبني شبكة تعمل بعد الحملة.");
}

// ═══ 8 · القناة التي يغفلها السوق ════════════════════════════════════════
{
  const s = slide("ما يميّزنا");
  heading(s, "حين يسأل المتسوّق مساعداً ذكياً بدل محرّك البحث",
    "صار المتسوّق يسأل «وش أفضل…» ويأخذ الإجابة دون أن يفتح نتيجة بحث واحدة.\nمن يُذكر داخل تلك الإجابة يكسب، ومن لا يُذكر يختفي — مهما أنفق على الإعلان.",
    { lh: 0.95 });

  const cw = (CW - 0.5) / 2;
  card(s, { x: M, y: 3.35, w: cw, h: 2.6, accent: true });
  s.addText("محرّكات بحث\nالجيل القادم", ar({
    x: M + 0.4, y: 3.7, w: cw - 0.8, h: 1.0, fontSize: 27, bold: true,
    color: ACC, lineSpacingMultiple: 1.15, margin: 0 }));
  s.addText("صفحاتنا تُقتبَس اليوم داخل إجابات المساعدين الأذكياء، وحضورنا فيها في تصاعد مستمرّ — والاقتباس يسبق المنافسة على نتائج البحث أصلاً.",
    ar({ x: M + 0.4, y: 4.78, w: cw - 0.8, h: 1.0, fontSize: 12.5, color: DIM,
      lineSpacingMultiple: 1.3, margin: 0 }));

  const x2 = M + cw + 0.5;
  card(s, { x: x2, y: 3.35, w: cw, h: 2.6 });
  s.addText("لماذا هذا صعب على غيرنا", ar({
    x: x2 + 0.4, y: 3.62, w: cw - 0.8, h: 0.34, fontSize: 16, bold: true,
    color: "FFFFFF", margin: 0 }));
  s.addText("لا تُشترى هذه القناة بالإعلان ولا تُختصر بالميزانية:", ar({
    x: x2 + 0.4, y: 4.0, w: cw - 0.8, h: 0.3, fontSize: 12.5, color: DIM, margin: 0 }));
  s.addText([
    { text: "بنية مفتوحة صراحةً لزواحف المساعدات الذكية", options: { bullet: true, breakLine: true } },
    { text: "محتوى عربي أصلي قابل للاقتباس لا مترجم", options: { bullet: true, breakLine: true } },
    { text: "بيانات منظّمة على كل صفحة علامة", options: { bullet: true, breakLine: true } },
    { text: "وعمل تحريري متّسق بلا انقطاع — بنيناه مبكراً", options: { bullet: true } },
  ], ar({ x: x2 + 0.4, y: 4.4, w: cw - 0.8, h: 1.4, fontSize: 12.5, color: TEXT,
    paraSpaceAfter: 6, margin: 0 }));
  foot(s, 8);
  s.addNotes("هذه ورقتنا الأقوى مع علامة كبيرة: ميزانيتهم تشتري إعلاناً، ولا تشتري ذكراً داخل إجابة مساعد ذكي.");
}

// ═══ 9 · المبادئ ═════════════════════════════════════════════════════════
{
  const s = slide("الثقة قبل الأرقام");
  heading(s, "علامتك في يد لا تُتاجر بها",
    "التعامل مع طرف ثالث ينشر باسم علامتك مخاطرة قبل أن يكون فرصة — فهذه مبادئنا، نضعها أمامكم قبل أن تسألوا.",
    { th: 0.62, lh: 0.5 });

  const pr = [
    ["لا نشر لعرض غير محقّق", "كل عرض يُختبر قبل نشره ويُسحب فور انتهائه"],
    ["لا مزايدة على اسمك", "لا ننافسك على زائرك ولا نرفع تكلفة كلمتك"],
    ["عرضك وحده على صفحتك", "لا كود منافس ولا تحويل إليه، ولو كان خصمه أعلى"],
    ["الإسناد على أنظمتكم", "الكود يُسجَّل في نظام العمولة لديكم — فالرقم رقمكم"],
    ["سرّية تامة", "لا اسم ولا رقم يخرج منّا بلا إذن مكتوب، ونوقّع NDA"],
    ["تسويق نظيف فقط", "لا صفحات مضلّلة ولا حشو — ما يُبنى باسمك لا يعرّضك لعقوبة"],
  ];
  const cw = (CW - 0.8) / 3, chh = 1.42;
  pr.forEach(([t, b], i) => {
    const col = i % 3, row = (i / 3) | 0;
    const x = M + col * (cw + 0.4), y = 2.75 + row * (chh + 0.42);
    card(s, { x, y, w: cw, h: chh });
    disc(s, { x: x + cw - 0.72, y: y + 0.24, d: 0.4, label: "✓", size: 13 });
    s.addText(t, ar({ x: x + 0.3, y: y + 0.24, w: cw - 1.2, h: 0.32,
      fontSize: 13.5, bold: true, color: "FFFFFF", margin: 0 }));
    s.addText(b, ar({ x: x + 0.3, y: y + 0.6, w: cw - 0.6, h: 0.7,
      fontSize: 11, color: DIM, lineSpacingMultiple: 1.25, margin: 0 }));
  });
  foot(s, 9);
  s.addNotes("قف هنا. مدير التسويق يخاف من طرف ثالث أكثر مما يطمع في طلبات — نزع الخوف يفتح الباب.");
}

// ═══ 10 · نماذج التعاون ══════════════════════════════════════════════════
{
  const s = slide("كيف نتعاون");
  heading(s, "نماذج تناسب اختلاف الأهداف",
    "نبدأ عادةً بنموذج واحد لفترة محدودة، ثم يُوسَّع وفق النتيجة. التفاصيل والتسعير تُناقش حسب حجم الحملة ومدّتها.",
    { th: 0.62, lh: 0.5 });

  const md = [
    ["حملة موسمية", "باقة حول موسم بعينه: صفحة موسم، ومحتوى داعم، وإبراز في الواجهة، وتوزيع على قنواتنا"],
    ["رعاية محتوى", "إنتاج تحريري عربي حول فئتك، يخدم حضورك في البحث وفي إجابات المساعدات — ويبقى أصلاً لك"],
    ["عرض حصري لجمهورنا", "كود لكل شريحة أو فئة أو موسم، فينفصل الإسناد في نظامكم وتعرفون أيّها يبيع"],
    ["شراكة بالأداء", "تعاون قائم على النتيجة المحقّقة، بلا تكلفة مقدّمة — عبر آلية الإسناد التي تعتمدونها"],
  ];
  const cw = (CW - 0.5) / 2, chh = 1.45;
  md.forEach(([t, b], i) => {
    const col = i % 2, row = (i / 2) | 0;
    const x = M + col * (cw + 0.5), y = 2.7 + row * (chh + 0.4);
    card(s, { x, y, w: cw, h: chh, accent: i === 0 });
    cardText(s, { x: x + 0.35, y: y + 0.25, w: cw - 0.7, title: t, body: b,
      titleSize: 15.5, bodySize: 12, bodyH: 0.78 });
  });

  s.addShape(pres.ShapeType.roundRect, { x: M, y: 6.15, w: CW, h: 0.78,
    rectRadius: 0.11, fill: { color: ACC } });
  s.addText("ما نحتاجه منكم للانطلاق:  الهوية البصرية، ونبذة معتمدة، وتفاصيل العرض ومدّته، وجهة اتصال واحدة — بلا تكامل تقني ولا تعديل على متجركم.",
    ar({ x: M + 0.35, y: 6.15, w: CW - 0.7, h: 0.78, fontSize: 12.5, bold: true,
      color: ONACC, valign: "middle", lineSpacingMultiple: 1.25, margin: 0 }));
  foot(s, 10);
  s.addNotes("لا تدخل في التسعير هنا. قل: أرجع لكم بمقترح مكتوب بعد ما أفهم الهدف والموسم.");
}

// ═══ 11 · مسار العمل ═════════════════════════════════════════════════════
{
  const s = slide("مسار العمل");
  heading(s, "من هذا الاجتماع إلى أول نتيجة", null, { th: 0.6 });

  const steps = [
    ["جلسة تعارف قصيرة", "نفهم هدف الحملة والجمهور والموسم، ونقترح النموذج الأنسب — بلا التزام من طرفكم"],
    ["خطة نشر مكتوبة", "ما سيُنشر، وأين، ومتى — بعد الاجتماع بوقت قصير"],
    ["التنفيذ والإطلاق", "إنتاج المحتوى والصفحات والمواد البصرية، ثم الإطلاق على قنواتنا"],
    ["والقياس عندكم لا عندنا", "الكود الحصري يجعل كل طلب مسجّلاً في نظامكم — وأبسط بداية تجربة محدودة تقيسونها بأنفسكم"],
  ];
  steps.forEach(([t, b], i) => {
    const y = 2.1 + i * 1.12;
    const last = i === steps.length - 1;
    card(s, { x: M, y, w: CW, h: 0.95, accent: last });
    disc(s, { x: W - M - 1.0, y: y + 0.25, d: 0.46, label: i + 1 });
    s.addText(t, ar({ x: M + 0.35, y: y + 0.16, w: CW - 1.5, h: 0.32,
      fontSize: 15, bold: true, color: last ? ACC : "FFFFFF", margin: 0 }));
    s.addText(b, ar({ x: M + 0.35, y: y + 0.5, w: CW - 1.5, h: 0.36,
      fontSize: 12, color: DIM, margin: 0 }));
  });
  foot(s, 11);
  s.addNotes("اختم الشريحة بطلب واحد: تجربة محدودة المدّة بكود حصري. لا تطلب أكثر في الاجتماع الأول.");
}

// ═══ 12 · الخاتمة ════════════════════════════════════════════════════════
{
  const s = pres.addSlide();
  s.background = { color: BG };
  s.addImage({ path: LOGO, x: (W - 3.1) / 2, y: 1.0, w: 3.1, h: 3.1 / 1.551 });
  s.addText("لنبدأ بتجربة محدودة تقيسونها بأنفسكم", ar({
    x: 1.2, y: 3.35, w: W - 2.4, h: 0.65, fontSize: 30, bold: true,
    color: "FFFFFF", align: "center", margin: 0 }));
  s.addText("كود حصري لجمهورنا، وصفحة دائمة باسم علامتكم — والرقم الذي تقرّرون عليه رقمكم أنتم.",
    ar({ x: 1.8, y: 4.1, w: W - 3.6, h: 0.5, fontSize: 15, color: DIM,
      align: "center", margin: 0 }));

  const cw2 = (CW - 0.8) / 3;
  [["البريد الإلكتروني", "dealpulseksa@gmail.com"],
   ["واتساب", "0534448900"],
   ["الموقع", "dealpulseksa.com"]].forEach(([k, v], i) => {
    const x = M + i * (cw2 + 0.4);
    card(s, { x, y: 5.0, w: cw2, h: 1.0, accent: true });
    s.addText(k, ar({ x, y: 5.16, w: cw2, h: 0.28, fontSize: 10.5, bold: true,
      color: ACC, align: "center", margin: 0 }));
    s.addText(v, ar({ x, y: 5.46, w: cw2, h: 0.36, fontSize: 14, bold: true,
      color: "FFFFFF", align: "center", margin: 0 }));
  });
  s.addText("هذا العرض تعريفي بطبيعته ولا يُنشئ عرضاً أو التزاماً ملزماً؛ ونطاق أي تعاون وشروطه ومدّته وتسعيره تُحدَّد في اتفاق مستقل بين الطرفين.",
    ar({ x: M, y: 6.55, w: CW, h: 0.5, fontSize: 10, color: MUTE,
      align: "center", lineSpacingMultiple: 1.25, margin: 0 }));
  s.addNotes("اطلب شيئاً واحداً: موافقة مبدئية على تجربة محدودة بكود حصري. ثم أرسل الملف التعريفي بعد الاجتماع.");
}

pres.writeFile({ fileName: OUT }).then(() => {
  console.log("OK  " + OUT + "  (" + fs.statSync(OUT).size.toLocaleString() + " bytes)");
});
