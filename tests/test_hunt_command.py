import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.db.connection import init_db, get_db_connection
from src.services.user_service import create_user
from src.handlers.hunt import handle_hunt, handle_throw_ball, handle_run

async def run_hunt_test():
    await init_db()
    test_user_id = 987654321

    # 1. Setup user with balls
    await create_user(test_user_id, "hunt_tester", "Tester")

    # 2. Simulate /hunt
    mock_msg = MagicMock()
    mock_msg.from_user.id = test_user_id
    mock_msg.text = "/hunt"
    mock_msg.answer = AsyncMock()

    await handle_hunt(mock_msg)
    assert mock_msg.answer.called
    print("Test 1 Passed: /hunt triggered encounter generation.")

    # Check DB encounter
    conn = await get_db_connection()
    async with conn.execute("SELECT * FROM encounters WHERE user_id = ? AND status = 'active' ORDER BY created_at DESC LIMIT 1", (test_user_id,)) as cur:
        enc = await cur.fetchone()
        assert enc is not None
        encounter_id = enc["encounter_id"]
    await conn.close()

    # 3. Simulate Master Ball throw (guaranteed catch)
    # Give user 1 master ball
    conn = await get_db_connection()
    await conn.execute("INSERT OR REPLACE INTO user_inventory (user_id, item_id, item_type, quantity) VALUES (?, 'master', 'ball', 1)", (test_user_id,))
    await conn.commit()
    await conn.close()

    mock_query = MagicMock()
    mock_query.from_user.id = test_user_id
    mock_query.data = f"throw:{encounter_id}:master:{test_user_id}"
    mock_query.answer = AsyncMock()
    mock_query.message.edit_text = AsyncMock()

    await handle_throw_ball(mock_query)
    assert mock_query.message.edit_text.called

    # Verify caught Pokemon in user_pokemon
    conn = await get_db_connection()
    async with conn.execute("SELECT * FROM user_pokemon WHERE user_id = ?", (test_user_id,)) as cur:
        caught_pokes = await cur.fetchall()
        assert len(caught_pokes) > 0
    await conn.close()
    print("Test 2 Passed: Master ball caught wild Pokémon and persisted to user_pokemon.")

if __name__ == "__main__":
    asyncio.run(run_hunt_test())
