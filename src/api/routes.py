import asyncio
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.schemas import CreateItemRequest, DashboardMetricsSchema, TrackedItemSchema
from src.db.models import TrackedItem
from src.db.repositories import ItemRepository
from src.db.session import get_session
from src.services.cache_service import cache_service
from src.services.csv_service import generate_items_csv
from src.services.scraper_service import fetch_and_parse_price

router = APIRouter()
templates = Jinja2Templates(directory="src/templates")


def _serialize_item(item: TrackedItem) -> dict:
    sorted_history = sorted(item.history, key=lambda h: h.recorded_at)
    return {
        "id": item.id,
        "sku": item.sku,
        "title": item.title,
        "category": item.category,
        "target_url": item.target_url,
        "css_selector": item.css_selector,
        "current_price": float(item.current_price),
        "previous_price": float(item.previous_price)
        if item.previous_price is not None
        else None,
        "price_change_pct": item.price_change_pct,
        "in_stock": item.in_stock,
        "updated_at": item.updated_at.isoformat()
        if item.updated_at
        else datetime.now(timezone.utc).isoformat(),
        "history": [
            {
                "price": float(h.price),
                "recorded_at": h.recorded_at.isoformat(),
            }
            for h in sorted_history[-10:]
        ],
    }


@router.get("/", response_class=HTMLResponse, include_in_schema=False)
async def dashboard_page(request: Request) -> HTMLResponse:
    return templates.TemplateResponse(request, "dashboard.html")


@router.get("/api/metrics", response_model=DashboardMetricsSchema, tags=["Analytics"])
async def get_metrics(session: AsyncSession = Depends(get_session)) -> dict:
    cached = await cache_service.get_json("pulse:metrics")
    if cached is not None:
        cached["cache_hit"] = True
        return cached

    repo = ItemRepository(session)
    metrics = await repo.get_dashboard_metrics()
    await cache_service.set_json("pulse:metrics", metrics)
    metrics["cache_hit"] = False
    return metrics


@router.get("/api/items", response_model=list[TrackedItemSchema], tags=["Catalog"])
async def list_items(
    category: str | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[dict]:
    if category is None:
        cached = await cache_service.get_json("pulse:items")
        if cached is not None:
            return cached

    repo = ItemRepository(session)
    items = await repo.get_all_items(category=category)
    serialized = [_serialize_item(i) for i in items]

    if category is None:
        await cache_service.set_json("pulse:items", serialized)
    return serialized


@router.post(
    "/api/items", response_model=TrackedItemSchema, status_code=201, tags=["Catalog"]
)
async def add_tracked_item(
    payload: CreateItemRequest,
    session: AsyncSession = Depends(get_session),
) -> dict:
    repo = ItemRepository(session)
    try:
        item = await repo.create_item(
            sku=payload.sku.strip().upper(),
            title=payload.title.strip(),
            category=payload.category.strip(),
            target_url=payload.target_url.strip(),
            initial_price=payload.initial_price,
            css_selector=payload.css_selector.strip(),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=400, detail=f"Позиция с таким SKU уже существует: {exc}"
        ) from exc

    await cache_service.invalidate_all()
    full_item = await repo.get_by_id(item.id)
    assert full_item is not None
    return _serialize_item(full_item)


@router.post("/api/scrape", tags=["Scraper"])
async def trigger_scrape_all(session: AsyncSession = Depends(get_session)) -> dict:
    """Асинхронно опрашивает все целевые страницы конкурентов и обновляет историю цен."""
    repo = ItemRepository(session)
    items = await repo.get_all_items()

    async with httpx.AsyncClient() as client:
        tasks = [
            fetch_and_parse_price(
                client=client,
                url=item.target_url,
                css_selector=item.css_selector,
                current_price=float(item.current_price),
            )
            for item in items
        ]
        results = await asyncio.gather(*tasks)

    for item, (new_price, in_stock) in zip(items, results):
        await repo.update_item_price(item.id, new_price=new_price, in_stock=in_stock)

    await cache_service.invalidate_all()
    return {"status": "ok", "updated_count": len(items)}


@router.get("/api/export/csv", tags=["Export"])
async def export_catalog_csv(session: AsyncSession = Depends(get_session)) -> Response:
    repo = ItemRepository(session)
    items = await repo.get_all_items()
    csv_bytes = generate_items_csv(items)
    filename = f"price_pulse_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M')}.csv"

    return Response(
        content=csv_bytes,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
