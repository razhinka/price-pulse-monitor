from datetime import datetime, timezone
from src.db.models import TrackedItem
from src.services.csv_service import generate_items_csv


def test_generate_items_csv_encoding_and_structure():
    item = TrackedItem(
        id=1,
        sku="TEST-GPU-01",
        title="Тестовая видеокарта RTX 4070",
        category="Комплектующие",
        target_url="https://example.com/item",
        css_selector=".price",
        current_price=60000.0,
        previous_price=65000.0,
        in_stock=True,
        updated_at=datetime.now(timezone.utc),
    )

    csv_bytes = generate_items_csv([item])

    # Проверка UTF-8 BOM для корректного открытия в Excel без искажения кириллицы
    assert csv_bytes.startswith(b"\xef\xbb\xbf")
    decoded = csv_bytes.decode("utf-8-sig")
    assert "TEST-GPU-01" in decoded
    assert "Тестовая видеокарта RTX 4070" in decoded
    assert "-7.69%" in decoded
