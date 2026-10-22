import csv
import io

from src.db.models import TrackedItem


def generate_items_csv(items: list[TrackedItem]) -> bytes:
    """Генерирует CSV-отчет по отслеживаемым товарам и динамике цен."""
    output = io.StringIO()
    writer = csv.writer(output, delimiter=";")
    writer.writerow(
        [
            "ID",
            "SKU (Артикул)",
            "Наименование товара",
            "Категория",
            "Текущая цена (₽)",
            "Предыдущая цена (₽)",
            "Изменение (%)",
            "В наличии",
            "URL источника",
            "Обновлено (UTC)",
        ]
    )

    for item in items:
        writer.writerow(
            [
                item.id,
                item.sku,
                item.title,
                item.category,
                f"{float(item.current_price):.2f}",
                f"{float(item.previous_price):.2f}" if item.previous_price else "—",
                f"{item.price_change_pct:+.2f}%",
                "Да" if item.in_stock else "Нет",
                item.target_url,
                item.updated_at.strftime("%Y-%m-%d %H:%M") if item.updated_at else "—",
            ]
        )

    return output.getvalue().encode("utf-8-sig")
