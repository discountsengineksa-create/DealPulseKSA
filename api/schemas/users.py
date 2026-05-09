from typing import Optional, List
from pydantic import BaseModel, Field


class UserSyncRequest(BaseModel):
    """تزامن مستخدم Firebase مع جدول web_users — يُستدعى بعد نجاح OTP."""
    firebase_uid: str = Field(..., min_length=1, max_length=128)
    phone_number: str = Field(..., pattern=r"^\+?[0-9]{8,16}$")
    display_name: Optional[str] = Field(None, max_length=100)
    email: Optional[str] = Field(None, max_length=200)
    user_agent: Optional[str] = Field(None, max_length=500)
    device_type: Optional[str] = Field(None, max_length=50)


class UserResponse(BaseModel):
    id: int
    phone_number: str
    display_name: Optional[str]
    email: Optional[str]
    country: Optional[str]
    city: Optional[str]
    lang: str
    visited_clicks: int = 0
    store_copy_count: int = 0
    manual_favorites: List[str] = []


class FavoriteRequest(BaseModel):
    store_id: str = Field(..., min_length=1, max_length=200)


class FavoritesResponse(BaseModel):
    favorites: List[str]
