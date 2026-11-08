import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.db.connection import init_db, get_db_connection
from src.services.user_service import create_user
from src.handlers.mybag import handle_mybag, handle_bag_filter

async def run_mybag_test():
    await init_db()
    test_user_id = 7766554433
    await create_user(test_user_id, "bag_trainer", "Brock")

    # 1. Test /mybag
    mock_msg = MagicMock()
    mock_msg.from_user.id = test_user_id
    mock_msg.text = "/mybag"
    mock_msg.answer = AsyncMock()

    await handle_mybag(mock_msg)
    assert mock_msg.answer.called
    args, kwargs = mock_msg.answer.call_args
    bag_text = args[0]
    assert "Brock's Adventure Bag" in bag_text
    assert "PokéCoins" in bag_text
    print("Test 1 Passed: /mybag rendered correctly.")

    # 2. Test category filtering callback (Balls)
    mock_query = MagicMock()
    mock_query.from_user.id = test_user_id
    mock_query.data = f"bag:ball:{test_user_id}"
    mock_query.answer = AsyncMock()
    mock_query.message.edit_text = AsyncMock()

    await handle_bag_filter(mock_query)
    assert mock_query.message.edit_text.called
    print("Test 2 Passed: /mybag category filter works seamlessly.")

if __name__ == "__main__":
    asyncio.run(run_mybag_test())
