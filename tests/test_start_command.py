import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.db.connection import init_db, get_db_connection
from src.handlers.start import handle_start, handle_starter_selection
from src.services.user_service import get_user

async def run_start_test():
    await init_db()

    # Clean test user if exists
    test_user_id = 1122334455
    conn = await get_db_connection()
    await conn.execute("DELETE FROM users WHERE telegram_id = ?", (test_user_id,))
    await conn.commit()
    await conn.close()

    # 1. Simulate new user /start
    mock_msg = MagicMock()
    mock_msg.from_user.id = test_user_id
    mock_msg.from_user.username = "red_trainer"
    mock_msg.from_user.first_name = "Red"
    mock_msg.text = "/start"
    mock_msg.answer = AsyncMock()

    await handle_start(mock_msg)
    assert mock_msg.answer.called
    print("Test 1 Passed: New user welcome message sent.")

    # 2. Simulate Starter Selection callback (Charmander)
    mock_query = MagicMock()
    mock_query.from_user.id = test_user_id
    mock_query.from_user.username = "red_trainer"
    mock_query.from_user.first_name = "Red"
    mock_query.data = f"starter_charmander_{test_user_id}"
    mock_query.answer = AsyncMock()
    mock_query.message.edit_text = AsyncMock()

    await handle_starter_selection(mock_query)
    assert mock_query.message.edit_text.called
    print("Test 2 Passed: Starter selected and registration completed.")

    # Verify user exists in database with starter pokemon and initial balls
    user = await get_user(test_user_id)
    assert user is not None
    assert user["first_name"] == "Red"

    conn = await get_db_connection()
    async with conn.execute("SELECT * FROM user_pokemon WHERE user_id = ?", (test_user_id,)) as cur:
        poke = await cur.fetchone()
        assert poke is not None
        assert poke["species_name"] == "Charmander"
        assert poke["level"] == 5

    async with conn.execute("SELECT * FROM user_inventory WHERE user_id = ? AND item_id = 'regular'", (test_user_id,)) as cur:
        balls = await cur.fetchone()
        assert balls is not None
        assert balls["quantity"] == 15

    await conn.close()
    print("Test 3 Passed: User, Starter Pokemon, and Inventory verified in DB.")

if __name__ == "__main__":
    asyncio.run(run_start_test())
