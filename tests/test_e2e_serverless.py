import asyncio
from unittest.mock import AsyncMock, patch
from aiogram.methods import SendMessage, EditMessageText, AnswerCallbackQuery
from app import process_telegram_update
from src.db.connection import init_db, get_db_connection
from src.bot.setup import bot
import config

async def test_serverless_e2e():
    await init_db()

    # 1. Test secret token protection
    res = await process_telegram_update({"update_id": 100}, secret_token="wrong_secret")
    assert res["status"] == "error"
    print("Test 1 Passed: Secret token protection validated.")

    # 2. Test valid update with secret token, mocking bot.__call__
    with patch.object(bot, "__call__", new_callable=AsyncMock) as mock_bot_call:
        mock_bot_call.return_value = True
        update_data = {
            "update_id": 101,
            "message": {
                "message_id": 1,
                "date": 1600000000,
                "chat": {"id": 888111, "type": "private"},
                "from": {"id": 888111, "is_bot": False, "first_name": "Serena", "username": "serena_kalos"},
                "text": "/start"
            }
        }
        res2 = await process_telegram_update(update_data, secret_token=config.WEBHOOK_SECRET)
        assert res2["status"] == "ok", f"Expected ok, got {res2}"
        print("Test 2 Passed: /start update processed via serverless pipeline.")

        # 3. Test Idempotency (replay same update_id 101)
        res3 = await process_telegram_update(update_data, secret_token=config.WEBHOOK_SECRET)
        assert res3["status"] == "ok"
        assert res3.get("message") == "Duplicate skipped"
        print("Test 3 Passed: Idempotency confirmed, duplicate update dropped.")

    # 4. Verify original database integrity
    # Make sure pokeplay.sqlite was completely untouched
    import sqlite3
    con = sqlite3.connect("pokeplay.sqlite")
    cur = con.cursor()
    cur.execute("SELECT count(*) FROM users")
    count = cur.fetchone()[0]
    assert count == 4128, f"Original database altered! Expected 4128, got {count}"
    print(f"Test 4 Passed: Original pokeplay.sqlite verified untouched ({count} users preserved).")

if __name__ == "__main__":
    asyncio.run(test_serverless_e2e())
