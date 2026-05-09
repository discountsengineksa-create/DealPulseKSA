"""Schemas للـ /users endpoints (المفضلة)."""
from typing import List
from pydantic import BaseModel, Field


class FavoriteRequest(BaseModel):
    store_id: str = Field(..., min_length=1, max_length=200)


class FavoritesResponse(BaseModel):
    favorites: List[str]
