from datetime import datetime, timedelta, timezone
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.db.models import TrackedItem, PriceHistory


class ItemRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_all_items(self, category: str | None = None) -> list[TrackedItem]:
        stmt = select(TrackedItem).options(selectinload(TrackedItem.history)).order_by(TrackedItem.id)
        if category:
            stmt = stmt.where(TrackedItem.category == category)
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_id(self, item_id: int) -> TrackedItem | None:
        stmt = (
            select(TrackedItem)
            .options(selectinload(TrackedItem.history))
            .where(TrackedItem.id == item_id)
        )
        return (await self.session.execute(stmt)).scalar_one_or_none()

    async def create_item(
        self,
        sku: str,
        title: str,
        category: str,
        target_url: str,
        initial_price: float,
        css_selector: str = ".price_color",
    ) -> TrackedItem:
        item = TrackedItem(
            sku=sku,
            title=title,
            category=category,
            target_url=target_url,
            css_selector=css_selector,
            current_price=initial_price,
            previous_price=initial_price,
            in_stock=True,
        )
        self.session.add(item)
        await self.session.flush()

        self.session.add(PriceHistory(item_id=item.id, price=initial_price))
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def update_item_price(self, item_id: int, new_price: float, in_stock: bool = True) -> TrackedItem | None:
        item = await self.get_by_id(item_id)
        if item is None:
            return None

        item.previous_price = float(item.current_price)
        item.current_price = new_price
        item.in_stock = in_stock
        item.updated_at = datetime.now(timezone.utc)

        self.session.add(PriceHistory(item_id=item.id, price=new_price))
        await self.session.commit()
        await self.session.refresh(item)
        return item

    async def get_dashboard_metrics(self) -> dict[str, int | float]:
        """Агрегатные метрики по каталогу конкурентов для аналитических карточек."""
        total_stmt = select(func.count(TrackedItem.id))
        avg_stmt = select(func.coalesce(func.avg(TrackedItem.current_price), 0.0))
        drops_stmt = select(func.count(TrackedItem.id)).where(
            TrackedItem.current_price < TrackedItem.previous_price
        )
        hikes_stmt = select(func.count(TrackedItem.id)).where(
            TrackedItem.current_price > TrackedItem.previous_price
        )

        total_items = (await self.session.execute(total_stmt)).scalar_one()
        avg_price = float((await self.session.execute(avg_stmt)).scalar_one())
        price_drops = (await self.session.execute(drops_stmt)).scalar_one()
        price_hikes = (await self.session.execute(hikes_stmt)).scalar_one()

        return {
            "total_items": total_items,
            "avg_price": round(avg_price, 2),
            "price_drops": price_drops,
            "price_hikes": price_hikes,
        }


async def seed_demo_catalog(session: AsyncSession) -> None:
    """Наполняет БД стартовыми товарами и историей цен для демонстрации графиков."""
    count = (await session.execute(select(func.count(TrackedItem.id)))).scalar_one()
    if count > 0:
        return

    now = datetime.now(timezone.utc)
    demo_data = [
        {
            "sku": "GPU-RTX4070S-12G",
            "title": "Видеокарта GeForce RTX 4070 Super 12GB",
            "category": "Комплектующие ПК",
            "target_url": "https://books.toscrape.com/catalogue/a-light-in-the-attic_1000/index.html",
            "prices": [68990.00, 67500.00, 66900.00, 64990.00],
        },
        {
            "sku": "CPU-RYZEN7-7800X3D",
            "title": "Процессор AMD Ryzen 7 7800X3D OEM",
            "category": "Комплектующие ПК",
            "target_url": "https://books.toscrape.com/catalogue/tipping-the-velvet_999/index.html",
            "prices": [39500.00, 41200.00, 42000.00, 43490.00],
        },
        {
            "sku": "SSD-SAMSUNG-990PRO-2T",
            "title": "NVMe Накопитель Samsung 990 PRO 2TB",
            "category": "Хранение данных",
            "target_url": "https://books.toscrape.com/catalogue/soumission_998/index.html",
            "prices": [19990.00, 19500.00, 18900.00, 18490.00],
        },
        {
            "sku": "MON-LG-27GR83Q-OLED",
            "title": "Монитор 27\" LG UltraGear 240Hz QHD",
            "category": "Периферия",
            "target_url": "https://books.toscrape.com/catalogue/sharp-objects_997/index.html",
            "prices": [45990.00, 45990.00, 44500.00, 44500.00],
        },
    ]

    for entry in demo_data:
        prices = entry["prices"]
        item = TrackedItem(
            sku=entry["sku"],
            title=entry["title"],
            category=entry["category"],
            target_url=entry["target_url"],
            css_selector=".price_color",
            previous_price=prices[-2],
            current_price=prices[-1],
            in_stock=True,
        )
        session.add(item)
        await session.flush()

        for idx, p in enumerate(prices):
            point_time = now - timedelta(days=(len(prices) - 1 - idx))
            session.add(PriceHistory(item_id=item.id, price=p, recorded_at=point_time))

    await session.commit()
