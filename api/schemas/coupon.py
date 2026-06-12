from pydantic import BaseModel, Field


class ExtraCoupon(BaseModel):
    """كود إضافي للمتجر (عرض مستقل بكوبون/خصم/عرض إضافي)."""
    public_coupon: str | None = None
    discount_value: str | None = None
    extra_offer: str | None = None
    extra_offer_en: str | None = None


class StoreResult(BaseModel):
    id: int
    store_id: str
    name_en: str | None = None
    affiliate_link: str | None = None
    public_coupon: str | None = None
    extra_offer: str | None = None
    extra_offer_en: str | None = None
    store_bio: str | None = None
    store_bio_en: str | None = None
    description: str | None = None
    discount_value: str | None = None
    store_tags: list[str] = Field(default_factory=list)
    store_tags_en: list[str] = Field(default_factory=list)
    is_trending: str | None = None
    is_promoted: bool = False
    logo_url: str | None = None
    cloaked_slug: str | None = None   # Week 4 — يبني المستهلك /go/{cloaked_slug}
    story_ring_color: str | None = None   # لون حلقة الستوري العادي (gold/silver/...) — None=تلقائي
    story_slides: list[str] = Field(default_factory=list)   # شرائح الستوري (فيديو/صورة) بالترتيب
    extra_coupons: list[ExtraCoupon] = Field(default_factory=list)   # أكواد إضافية للمتجر
    total_coupon_copies: int = 0
    total_link_clicks: int = 0
    # «الأكثر طلباً» = نقرات + نسخ + عدد البحث + عدد المفضّلين (يُحسب في SQL).
    popularity_score: int = 0
    score_pct: int = 0


class SearchResponse(BaseModel):
    query: str
    total: int
    capped: bool   # True إذا وصلت النتائج للحد الأقصى (50)
    results: list[StoreResult]
