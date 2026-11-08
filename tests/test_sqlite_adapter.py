import asyncio
import os
import pytest
from src.db.connection import init_db, get_db_connection

async def test_db():
    await init_db()
    conn = await get_db_connection()
    try:
        # Insert test user
        await conn.execute(
            "INSERT OR REPLACE INTO users (telegram_id, username, first_name) VALUES (?, ?, ?)",
            (999999999, "ash_ketchum", "Ash")
        )
        await conn.commit()

        async with conn.execute("SELECT * FROM users WHERE telegram_id = ?", (999999999,)) as cursor:
            row = await cursor.fetchone()
            assert row is not None
            assert row["username"] == "ash_ketchum"
            assert row["coins"] == 1000
            print("DB smoke test passed: User verified")
    finally:
        await conn.close()

if __name__ == "__main__":
    asyncio.run(test_db())
