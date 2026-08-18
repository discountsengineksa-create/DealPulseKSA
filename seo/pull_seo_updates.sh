#!/usr/bin/env bash
# سحب تحديثات SEO الرسمية — المصادر الأولية أولاً، بلا تفسير طرف ثالث.
# التشغيل: bash seo/pull_seo_updates.sh [عدد العناوين]
# الأحكام والمصادر المرفوضة: seo/learning_sources.md
set -u
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
N="${1:-8}"

feed () {  # $1=اسم  $2=رابط
  echo ""
  echo "═══ $1 ═══"
  local out
  out=$(curl -s -L --max-time 30 -A "$UA" --compressed "$2" \
        | grep -o "<title>[^<]*</title>" | sed 's/<[^>]*>//g' | tail -n +2 | head -"$N")
  if [ -z "$out" ]; then echo "  ⚠️ لا مخرَج — المصدر محجوب أو غيّر شكله. تحقّق يدوياً."
  else echo "$out" | sed 's/^/  · /'; fi
}

echo "═══ ١) تحديثات ترتيب جوجل الرسمية — مؤرَّخة، بلا تفسير ═══"
curl -s -L --max-time 30 "https://status.search.google.com/incidents.json" \
  | tr '}' '\n' | grep -o '"begin":"[^"]*"\|"external_desc":"[^"]*"' \
  | sed 's/"begin":"/  التاريخ: /; s/"external_desc":"/  الحدث : /; s/"$//' | head -$((N*2))

feed "٢) مدوّنة Google Search Central — المصدر الأول" "https://developers.google.com/search/blog/feed.xml"
feed "٣) Search Engine Land"    "https://searchengineland.com/feed"
feed "٤) Search Engine Journal" "https://www.searchenginejournal.com/feed/"
feed "٥) Ahrefs Blog"           "https://ahrefs.com/blog/feed/"
feed "٦) Marie Haynes"          "https://www.mariehaynes.com/feed/"

echo ""
echo "⛔ Search Engine Roundtable محجوب برمجياً (Cloudflare يرجّع صفر بايت) — بالمتصفّح فقط."
echo "⚠️ كل ما فوق مادة خام. لا يُنفَّذ سطر قبل المرور على seo/external_advice_filter.md"
