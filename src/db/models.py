from datetime import datetime
from sqlalchemy import String, Numeric, ForeignKey, DateTime, Boolean, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class TrackedItem(Base):
    __tablename__ = "tracked_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    target_url: Mapped[str] = mapped_column(String(512), nullable=False)
    css_selector: Mapped[str] = mapped_column(String(128), default=".price_color", nullable=False)
    current_price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    previous_price: Mapped[float | None] = mapped_column(Numeric(12, 2), nullable=True)
    in_stock: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )

    history: Mapped[list["PriceHistory"]] = relationship(
        back_populates="item",
        cascade="all, delete-orphan",
        order_by="PriceHistory.recorded_at.desc()",
    )

    @property
    def price_change_pct(self) -> float:
        """Вычисляет процент изменения цены относительно прошлого замера."""
        if not self.previous_price or float(self.previous_price) == 0:
            return 0.0
        curr = float(self.current_price)
        prev = float(self.previous_price)
        return round(((curr - prev) / prev) * 100, 2)


class PriceHistory(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    item_id: Mapped[int] = mapped_column(
        ForeignKey("tracked_items.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    price: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        index=True,
    )

    item: Mapped["TrackedItem"] = relationship(back_populates="history")
