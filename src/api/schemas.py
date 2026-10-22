from datetime import datetime

from pydantic import BaseModel, Field


class PricePointSchema(BaseModel):
    price: float
    recorded_at: datetime


class TrackedItemSchema(BaseModel):
    id: int
    sku: str
    title: str
    category: str
    target_url: str
    css_selector: str
    current_price: float
    previous_price: float | None
    price_change_pct: float
    in_stock: bool
    updated_at: datetime
    history: list[PricePointSchema] = []


class CreateItemRequest(BaseModel):
    sku: str = Field(..., min_length=2, max_length=64, examples=["GPU-RTX4080S"])
    title: str = Field(
        ...,
        min_length=3,
        max_length=255,
        examples=["Видеокарта GeForce RTX 4080 Super"],
    )
    category: str = Field(
        ..., min_length=2, max_length=100, examples=["Комплектующие ПК"]
    )
    target_url: str = Field(
        default="https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
        max_length=512,
    )
    css_selector: str = Field(default=".price_color", max_length=128)
    initial_price: float = Field(..., gt=0, examples=[94990.0])


class DashboardMetricsSchema(BaseModel):
    total_items: int
    avg_price: float
    price_drops: int
    price_hikes: int
    cache_hit: bool = False
