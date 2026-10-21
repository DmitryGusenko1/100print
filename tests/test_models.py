from app.database.models import MemoryItem


def test_memory_item_preserves_original_text() -> None:
    original = "  Важная мысль пользователя  "
    item = MemoryItem(
        source="test",
        type="thought",
        original_text=original,
        normalized_text=original.strip(),
        importance=0.5,
        status="active",
        metadata_={},
    )
    assert item.original_text == original
    assert item.normalized_text == "Важная мысль пользователя"
