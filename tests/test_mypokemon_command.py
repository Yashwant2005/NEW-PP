import asyncio
from unittest.mock import AsyncMock, MagicMock
from src.db.connection import init_db, get_db_connection
from src.services.user_service import create_user, give_starter_pokemon
from src.handlers.mypokemon import handle_mypokemon, handle_pokemon_page

async def run_mypokemon_test():
    await init_db()
    test_user_id = 5544332211
    await create_user(test_user_id, "poke_collector", "Misty")
    await give_starter_pokemon(test_user_id, "squirtle")

    # 1. Test /mypokemon
    mock_msg = MagicMock()
    mock_msg.from_user.id = test_user_id
    mock_msg.text = "/mypokemon"
    mock_msg.answer = AsyncMock()

    await handle_mypokemon(mock_msg)
    assert mock_msg.answer.called
    args, kwargs = mock_msg.answer.call_args
    poke_text = args[0]
    assert "Misty's Pokémon Collection" in poke_text
    assert "Squirtle" in poke_text
    print("Test 1 Passed: /mypokemon rendered collection correctly.")

    # 2. Test sort callback (IV)
    mock_query = MagicMock()
    mock_query.from_user.id = test_user_id
    mock_query.data = f"poke_page:1:iv_desc:{test_user_id}"
    mock_query.answer = AsyncMock()
    mock_query.message.edit_text = AsyncMock()

    await handle_pokemon_page(mock_query)
    assert mock_query.message.edit_text.called
    print("Test 2 Passed: /mypokemon pagination and sorting callback works.")

if __name__ == "__main__":
    asyncio.run(run_mypokemon_test())
