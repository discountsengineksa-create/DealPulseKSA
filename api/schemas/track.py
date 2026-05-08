from typing import Literal
from pydantic import BaseModel, Field


class TrackRequest(BaseModel):
    user_id: int   = Field(..., gt=0, description="Telegram ID للمستخدم")
    store_id: str  = Field(..., min_length=1, max_length=200)
    action: Literal["click_link", "copy_coupon", "search"]
    details: str | None = Field(None, max_length=500)


class TrackResponse(BaseModel):
    ok: bool
    action: str
    store_id: str
