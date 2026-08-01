---
name: windsor_gsc_connector
description: Windsor MCP فيه Search Console + Instagram موصولان، لكن الخطة المجانية تسمح بحساب واحد فتُحجب القراءة
metadata: 
  node_type: memory
  type: reference
  originSessionId: c62855b1-ac5e-43c8-b626-e7e183f2c621
  modified: 2026-08-01T04:40:30.818Z
---

**Windsor.ai MCP** موصول بحسابين: `searchconsole` (`https://www.dealpulseksa.com/`) و
`instagram` (`17841444145819859` — كوبونات خصم نبض الصفقات).

**المطبّ:** الخطة المجانية تسمح بحساب واحد، فأي `get_data` يرجع **صفوفاً وهمية** نصّها
`"Uh-oh! You've connected more accounts than your Free plan allows"` مع أصفار — **لا يرجع
خطأ**. أي تحليل يبني على هذا الردّ بلا قراءته يخرج بأرقام صفرية كاذبة (تحقّقت 1 أغسطس 2026).

**الحل:** فكّ ربط إنستغرام من Windsor لتحرير الخانة لـSearch Console (أهمّ مصدر: استعلامات/
صفحات/مراكز GSC — نفس البيانات في [[seo_page_portfolio_verdict]] و [[seo_indexation_status]])،
أو الترقية. حقول GSC المتاحة: `query`, `pagepath`, `clicks`, `impressions`, `position`,
`country`, `device`, `branded_vs_nonbranded`, `search_appearance` — استدعِ `get_fields` قبل
`get_data` دائماً.
