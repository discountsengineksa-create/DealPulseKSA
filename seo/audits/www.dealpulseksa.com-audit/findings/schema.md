# Schema.org Audit — www.dealpulseksa.com

Audited: 2026-08-10. Method: `claude-seo run render_page.py <URL> --mode never --json-ld-output <file>` (server-rendered HTML, no Playwright needed — confirmed raw HTML carries the JSON-LD directly). Three page types sampled: store page (given, re-verified), blog article, `/calendar`.

Site context for judgment calls below: DealPulseKSA is an **affiliate publisher**, not a merchant. It does not sell, ship, or fulfill anything — it links/refers to third-party stores' discount codes. That distinction matters for every "should we add Offer/Product schema" question below.

## 1. Detection Results

### 1a. Store page — `/store/سويتر` (re-verified, matches the pre-supplied count exactly)

**2 JSON-LD blocks**, `total_bytes: 2410`, both `valid: true`.

**Block 1** (`ContactPoint`, `Country`, `EntryPoint`, `ImageObject`, `OnlineBusiness`, `Organization`, `PostalAddress`, `SearchAction`, `WebSite` — a `@graph` of 3 nodes):

```json
{
  "@context": "https://schema.org",
  "@graph": [
    {
      "@type": "Organization",
      "@id": "https://www.dealpulseksa.com/#organization",
      "name": "نبض الصفقات",
      "alternateName": "Deal Pulse KSA",
      "url": "https://www.dealpulseksa.com",
      "logo": { "@type": "ImageObject", "url": "https://www.dealpulseksa.com/logo.png", "width": 512, "height": 512 },
      "description": "منصة كوبونات الخصم الأذكى في المملكة العربية السعودية",
      "foundingDate": "2026",
      "areaServed": { "@type": "Country", "name": "Saudi Arabia", "identifier": "SA" },
      "contactPoint": [
        { "@type": "ContactPoint", "contactType": "customer support", "email": "dealpulseksa@gmail.com", "availableLanguage": ["Arabic", "English"], "areaServed": "SA" },
        { "@type": "ContactPoint", "contactType": "sales", "email": "dealpulseksa@gmail.com", "availableLanguage": ["Arabic", "English"], "areaServed": "SA" }
      ],
      "sameAs": ["https://t.me/DealPulseksa_bot", "https://www.instagram.com/dealpulseksa", "https://x.com/dealpulseksa", "https://www.facebook.com/dealpulseksa", "https://www.threads.net/@dealpulseksa"],
      "address": { "@type": "PostalAddress", "addressCountry": "SA" }
    },
    {
      "@type": "WebSite",
      "@id": "https://www.dealpulseksa.com/#website",
      "url": "https://www.dealpulseksa.com",
      "name": "نبض الصفقات | Deal Pulse KSA",
      "inLanguage": ["ar-SA", "en-US"],
      "publisher": { "@id": "https://www.dealpulseksa.com/#organization" },
      "potentialAction": { "@type": "SearchAction", "target": { "@type": "EntryPoint", "urlTemplate": "https://www.dealpulseksa.com/stores?q={search_term_string}" }, "query-input": "required name=search_term_string" }
    },
    {
      "@type": "OnlineBusiness",
      "@id": "https://www.dealpulseksa.com/#localbusiness",
      "name": "نبض الصفقات | Deal Pulse KSA",
      "url": "https://www.dealpulseksa.com",
      "image": "https://www.dealpulseksa.com/logo.png",
      "logo": "https://www.dealpulseksa.com/logo.png",
      "parentOrganization": { "@id": "https://www.dealpulseksa.com/#organization" },
      "areaServed": { "@type": "Country", "name": "Saudi Arabia", "identifier": "SA" },
      "address": { "@type": "PostalAddress", "addressCountry": "SA" }
    }
  ]
}
```

**Block 2** (`BreadcrumbList` + 3 `ListItem`):

```json
{
  "@context": "https://schema.org",
  "@type": "BreadcrumbList",
  "itemListElement": [
    { "@type": "ListItem", "position": 1, "name": "الرئيسية", "item": "https://www.dealpulseksa.com/" },
    { "@type": "ListItem", "position": 2, "name": "المتاجر", "item": "https://www.dealpulseksa.com/stores" },
    { "@type": "ListItem", "position": 3, "name": "سويتر", "item": "https://www.dealpulseksa.com/store/%D8%B3%D9%88%D9%8A%D8%AA%D8%B1" }
  ]
}
```

**Absent on this page**: `Offer` (0 instances — no discount/code entity, despite a visible code on the page), `FAQPage`/`QAPage` (0 instances — despite two visible Q&A pairs on the page), `Product`/`Service` (0 — no entity for the merchant itself), and no `WebPage` node (unlike the blog/calendar templates below, which both carry one).

### 1b. Blog article — `/blog/alibaba-camping-outdoor-gear-wholesale-saudi-arabia` — verified: **4 blocks**, confirming the pre-supplied count

`block_count: 4, total_bytes: 5250`, all `valid: true`.

1. Same `Organization`/`WebSite`/`OnlineBusiness` `@graph` as the store page (2001 bytes, identical `@id`s — good, consistent entity reuse across the site).
2. `BlogPosting` (893 bytes):
```json
{
  "@context": "https://schema.org",
  "@type": "BlogPosting",
  "mainEntityOfPage": { "@type": "WebPage", "@id": "https://www.dealpulseksa.com/blog/alibaba-camping-outdoor-gear-wholesale-saudi-arabia" },
  "headline": "شراء معدّات التخييم والكشتة بالجملة من علي بابا 2026 — لسوق الرحلات السعودي",
  "description": "دليل استيراد خيام وكراسي ومعدّات التخييم والكشتة بالجملة من Alibaba.com...",
  "datePublished": "2026-07-08",
  "dateModified": "2026-07-08",
  "image": "https://www.dealpulseksa.com/logo.png",
  "inLanguage": "ar-SA",
  "author": { "@type": "Organization", "name": "فريق نبض الصفقات", "url": "https://www.dealpulseksa.com" },
  "publisher": { "@id": "https://www.dealpulseksa.com/#organization" }
}
```
3. `BreadcrumbList` (707 bytes, 4-level: home → blog → category → article).
4. `ItemList` (1649 bytes) — 6 related-post `ListItem`s (each with `url` + `name`, no nested `item` wrapper) — a "related articles" widget.

### 1c. `/calendar` — verified: **5 blocks**, confirming the pre-supplied count

`block_count: 5, total_bytes: 10198`, all `valid: true`.

1. Same `Organization`/`WebSite`/`OnlineBusiness` `@graph` (2001 bytes, identical `@id`s).
2. `WebPage` (506 bytes) — **this is the node type missing from the store page**:
```json
{
  "@context": "https://schema.org",
  "@type": "WebPage",
  "name": "تقويم تخفيضات السعودية 2026",
  "description": "مواعيد أقوى مواسم التخفيضات في المملكة العربية السعودية.",
  "url": "https://www.dealpulseksa.com/calendar",
  "isPartOf": { "@id": "https://www.dealpulseksa.com/#website" },
  "publisher": { "@id": "https://www.dealpulseksa.com/#organization" },
  "inLanguage": "ar-SA",
  "datePublished": "2026-07-03T19:07:55+03:00",
  "dateModified": "2026-08-10T14:26:18.192Z"
}
```
3. `BreadcrumbList` (297 bytes, 2-level).
4. `ItemList` (2007 bytes) — 12 `ListItem`s, one per Saudi shopping season (White Friday, National Day, Ramadan, 11.11, etc.), each with `name` + fragment `url`. `numberOfItems: 12` matches `itemListElement.length` exactly.
5. `FAQPage` (5387 bytes) — 10 `Question`/`Answer` pairs on shopping-season timing (Ramadan dates, White Friday vs Black Friday, whether discounts are real, code-stacking, etc.).

## 2. Validation Results

| Block | Page | Result | Notes |
|---|---|---|---|
| Organization/WebSite/OnlineBusiness `@graph` | all 3 sampled pages | **PASS** | `@context` = `https://schema.org` ✓; all URLs absolute ✓; required props (`name`, `url`) present on every node ✓; `logo` correctly typed as `ImageObject` with dimensions ✓; `SearchAction.target.urlTemplate` uses the correct `{search_term_string}` placeholder pattern ✓; no placeholder text ✓. Reused via `@id` across pages instead of re-declared inline — correct pattern, avoids duplicate-entity ambiguity. |
| `OnlineBusiness` type choice | same | **PASS with note (Low)** | `OnlineBusiness` is the right `LocalBusiness` subtype for a site with no physical premises — better fit than plain `LocalBusiness`. `PostalAddress` deliberately carries only `addressCountry: "SA"` (no street/locality), which is correct for an online-only business, not a missing-property defect. |
| `BreadcrumbList` | all 3 | **PASS** | `position`, `name`, `item` (absolute URL) present on every `ListItem`; hierarchy matches visible breadcrumb UI on each page type. |
| `BlogPosting` | blog article | **PASS** | Required (`headline`, `datePublished`, `image`) and recommended (`author`, `publisher`, `dateModified`, `mainEntityOfPage`) all present. `dateModified` equals `datePublished` on this one sample — not a validity failure, but worth checking on a wider sample if "recently updated" claims matter for freshness signals; not re-derived here (out of scope, single-sample observation only). |
| `ItemList` (blog related-posts, calendar seasons) | blog, calendar | **PASS** | Valid `ListItem` structure (`position` + `url` + `name`). Calendar's `numberOfItems: 12` reconciles exactly with 12 `itemListElement` entries — no phantom-item mismatch. |
| `WebPage` | calendar | **PASS** | Carries `isPartOf`, `publisher`, `inLanguage`, `datePublished`, `dateModified` — this is the template the store page should also use (see §3). |
| `FAQPage` | calendar | **Flag: Info priority, not Critical** | Structurally valid (10 well-formed `Question`/`acceptedAnswer` pairs, no placeholder text). Per current plugin policy, Google retired FAQ rich results for all sites (May 7, 2026), so this produces **no SERP benefit** anymore. **Do not recommend removal** — any AI/GEO citability benefit from having clean, structured Q&A on a high-intent page is plausible but unconfirmed. Leave as-is. |
| `Offer` | store page | **Absent — flagged as missing opportunity, not a validation failure** (schema that doesn't exist can't fail validation). See §3. |
| `FAQPage`/`QAPage` | store page | **Absent.** Two visible Q&A pairs on the page carry no schema. See §3 for why this is judged differently from the calendar's FAQPage. |
| `Product`/merchant entity | store page | **Absent.** The only `Organization` on the page is DealPulseKSA itself (the publisher) — nothing in the JSON-LD names or identifies the merchant ("سويتر") that the page is actually about. See §3. |

## 3. Missing Opportunities — Store Page

The store page's 2 blocks describe **DealPulseKSA the publisher** (Organization/WebSite/OnlineBusiness) and **site navigation** (Breadcrumb). Nothing in the markup tells a machine reader what merchant this specific page covers, that it currently has an active discount code, or what the on-page Q&A answers. That's a real gap on a page whose entire content is "merchant X, code Y, two questions about it" — three of the page's core content elements have zero structured representation.

**No Google rich-result claim is being made for any of the below** — Google's coupon/discount structured-data feature requires Merchant Center enrollment and a submitted product/offer feed, not just on-page JSON-LD from a non-merchant affiliate site; that feature doesn't apply here regardless of markup quality. The justification is entity clarity and AI-citability: an LLM or AI crawler ingesting this page's JSON-LD currently gets zero signal about which store and which offer the page is about — only who publishes the page. Fixing that is a legitimate, non-deprecated, non-Google-rich-result-dependent improvement.

### 3a. `WebPage` node with `about` — fixes "who is this page about"

The blog and calendar pages both carry a `WebPage` node (§1b/§1c); the store page skips straight from the Organization graph to Breadcrumb. Bring it in line and use `about` to name the merchant as a distinct entity from the publisher:

```json
{
  "@context": "https://schema.org",
  "@type": "WebPage",
  "@id": "https://www.dealpulseksa.com/store/%D8%B3%D9%88%D9%8A%D8%AA%D8%B1#webpage",
  "url": "https://www.dealpulseksa.com/store/%D8%B3%D9%88%D9%8A%D8%AA%D8%B1",
  "name": "[إدراج عنوان الصفحة الفعلي — كوبونات وأكواد خصم سويتر]",
  "isPartOf": { "@id": "https://www.dealpulseksa.com/#website" },
  "publisher": { "@id": "https://www.dealpulseksa.com/#organization" },
  "inLanguage": "ar-SA",
  "dateModified": "[تاريخ آخر تحديث فعلي بصيغة ISO 8601]",
  "about": {
    "@type": "Organization",
    "name": "سويتر",
    "url": "[رابط الموقع الرسمي للمتجر — وليس رابط تتبّع]"
  }
}
```
Placeholders (`[...]`) must be filled with real values before publishing — do not ship literal placeholder text (validation checklist item 5).

### 3b. `Offer` for the discount code — with a deliberate omission

```json
{
  "@context": "https://schema.org",
  "@type": "Offer",
  "url": "https://www.dealpulseksa.com/store/%D8%B3%D9%88%D9%8A%D8%AA%D8%B1",
  "name": "[عنوان العرض الحالي كما يظهر في الصفحة]",
  "seller": {
    "@type": "Organization",
    "name": "سويتر",
    "url": "[رابط الموقع الرسمي للمتجر]"
  },
  "priceCurrency": "SAR",
  "price": "0",
  "availability": "https://schema.org/InStock",
  "validFrom": "[تاريخ البدء الفعلي — ISO 8601]",
  "validThrough": "[تاريخ الانتهاء الفعلي — ISO 8601]"
}
```

Two deliberate design choices, both worth stating explicitly:
- **`seller` is the merchant, not DealPulseKSA.** DealPulseKSA doesn't sell anything on this page — it refers. Setting `seller` to DealPulseKSA would misrepresent the commercial relationship; setting it to the actual merchant is both accurate and the correct entity-clarity signal.
- **The literal code string is deliberately excluded from the JSON-LD.** Coupon-code structured data conventions (Google's Merchant coupon-feed guidance) discourage embedding the raw code in crawlable structured data, since it lets scrapers harvest codes without visiting the page or respecting any click-gate the UI uses. Keep the code in the rendered page content only, behind whatever reveal/copy interaction the page already uses — do not add it to JSON-LD.

### 3c. Store-page Q&A — no schema recommendation, and here's why that's different from the calendar's FAQPage

The calendar's 10 Q&A pairs are general "when is White Friday" evergreen content — flagged Info per policy, kept as-is, no action either way.

The store page's two Q&A pairs are different in kind: they're short, code/merchant-specific canned copy ("does this code work on X," "when does it expire") written editorially, not a genuine user-submitted Q&A thread. That rules out `QAPage`, which per the plugin's hard rule is reserved for **genuine user Q&A** (Google's own guidance for `QAPage` expects multiple community-submitted answers, `upvoteCount`, `author`, etc. — none of which exists here since this is single-author editorial copy). It also rules out recommending `FAQPage` for the same reason `FAQPage` was flagged Info elsewhere: zero Google SERP benefit since May 2026, and any AI/GEO benefit is unconfirmed. **Net recommendation: leave the two Q&A pairs as plain content, no schema.** Marking them up would add markup surface with a hard "no SERP benefit" floor and only a speculative AI-citability upside — a materially weaker case than the `Offer`/`WebPage` recommendations above, which fix an actual entity-identification gap that exists independent of any rich-result question.

## 4. Summary Table

| Item | Status | Priority | Rationale |
|---|---|---|---|
| Store page: `WebPage` node with `about` (merchant entity) | Missing | **Medium** | Page has zero structured signal for which merchant it covers; blog/calendar already use this pattern |
| Store page: `Offer` for the active code | Missing | **Medium** | Entity-clarity/AI-citability only — no Google coupon rich result applies without Merchant Center enrollment |
| Store page: Q&A markup | Not recommended | — | Not genuine user Q&A (rules out `QAPage`); `FAQPage` has no SERP benefit post-May-2026 (rules out priority push) |
| Calendar: existing `FAQPage` | Present, valid | **Info** | No Google SERP benefit anymore; do not recommend removal |
| Blog: `BlogPosting` + `ItemList` | Present, valid | — | Passes validation as-is |
| `Organization`/`WebSite`/`OnlineBusiness` graph (site-wide) | Present, valid | — | Passes validation as-is; correctly reused via `@id` across page types |
| `HowTo`, `SpecialAnnouncement`, `CourseInfo`/`EstimatedSalary`/`LearningVideo` | Absent | — | Correctly absent — all deprecated/retired; do not add |

## Files Referenced

- Store page sample: `https://www.dealpulseksa.com/store/سويتر` (2 blocks, re-verified byte-identical to pre-supplied count)
- Blog sample: `https://www.dealpulseksa.com/blog/alibaba-camping-outdoor-gear-wholesale-saudi-arabia` (4 blocks, verified)
- `https://www.dealpulseksa.com/calendar` (5 blocks, verified)
- Raw JSON-LD extraction artifacts (bounded, this session's scratchpad): `store_jsonld.json`, `blog_jsonld.json`, `calendar_jsonld.json`
