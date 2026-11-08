import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.db.connection import init_db, get_db_connection
from src.services.user_service import create_user
from src.handlers.safari import handle_safari_zone, handle_safari_callbacks, handle_exit_cmd

async def run_safari_test():
    await init_db()
    test_user_id = 123459999

    # Clean user and ensure they have a pass
    conn = await get_db_connection()
    await conn.execute("DELETE FROM users WHERE telegram_id = ?", (test_user_id,))
    await conn.execute("DELETE FROM safari_sessions WHERE user_id = ?", (test_user_id,))
    await conn.commit()
    await conn.close()

    await create_user(test_user_id, "safari_tester", "Koga")

    # 1. Test /safari_zone view
    mock_msg = MagicMock()
    mock_msg.from_user.id = test_user_id
    mock_msg.text = "/safari_zone"
    mock_msg.answer = AsyncMock()

    await handle_safari_zone(mock_msg)
    assert mock_msg.answer.called
    print("Test 1 Passed: /safari_zone menu rendered.")

    # 2. Test Enter Safari callback
    mock_query = MagicMock()
    mock_query.from_user.id = test_user_id
    mock_query.data = f"safari:enter:kanto:{test_user_id}"
    mock_query.answer = AsyncMock()
    mock_query.message.edit_text = AsyncMock()

    await handle_safari_callbacks(mock_query)
    assert mock_query.message.edit_text.called

    # Check database state: session created and 30 safari balls granted
    conn = await get_db_connection()
    async with conn.execute("SELECT * FROM safari_sessions WHERE user_id = ? AND is_active = 1", (test_user_id,)) as cur:
        sess = await cur.fetchone()
        assert sess is not None
        assert sess["zone"] == "kanto"

    async with conn.execute("SELECT quantity FROM user_inventory WHERE user_id = ? AND item_id = 'safari'", (test_user_id,)) as cur:
        ball_row = await cur.fetchone()
        assert ball_row is not None
        assert ball_row["quantity"] == 30
    await conn.close()
    print("Test 2 Passed: Entered Safari, session active with 30 balls.")

    # 3. Test Exit Safari command
    mock_exit_msg = MagicMock()
    mock_exit_msg.from_user.id = test_user_id
    mock_exit_msg.text = "/exit"
    mock_exit_msg.answer = AsyncMock()

    await handle_exit_cmd(mock_exit_msg)

    conn = await get_db_connection()
    async with conn.execute("SELECT is_active FROM safari_sessions WHERE user_id = ?", (test_user_id,)) as cur:
        assert (await cur.fetchone())["is_active"] == 0
    await conn.close()
    print("Test 3 Passed: Exited Safari, session deactivated and balls cleaned up.")

if __name__ == "__main__":
    asyncio.run(run_safari_test())
