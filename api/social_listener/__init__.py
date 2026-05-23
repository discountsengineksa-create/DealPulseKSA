"""
Social Listener + Auto-Responder (Week 7-8).

  1. ingest.ingest_signal()      — يستقبل إشارة (mention) من منصة ويخزّنها.
  2. scorer.score_content()      — يطابق مصطلحات الرصد ويحسب intent_score.
  3. responder.prepare_response()— يرشّح متجراً، يبني رابط صفحة الهبوط، ويولّد
     ردّاً من قالب (A/B). الردود عالية الثقة تُعتمد تلقائياً (SOCIAL_AUTO_APPROVE).
  4. poster.post_response()      — ينشر الرد (عبر SOCIAL_POST_WEBHOOK) أو يعلّمه
     جاهزاً للاعتماد اليدوي من الداشبورد.

orchestrator: responder.process_new_signals() — يربط 2+3 ويُجدوَل كل بضع دقائق.
الاستقبال الفوري عبر POST /api/v1/social/ingest (للأتمتة الخارجية Zapier/Make).
"""
