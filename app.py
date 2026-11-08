import json
import logging
from contextlib import asynccontextmanager
from typing import Dict, Any
from aiogram.types import Update
from src.bot.setup import bot, dp
from src.db.connection import init_db, get_db_connection
from src.handlers import start, hunt, mybag, mypokemon, safari
import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pokeplay")

# Register routers
dp.include_router(start.router)
dp.include_router(hunt.router)
dp.include_router(mybag.router)
dp.include_router(mypokemon.router)
dp.include_router(safari.router)

async def process_telegram_update(update_data: Dict[str, Any], secret_token: str = "") -> Dict[str, Any]:
    """
    Serverless handler for incoming Telegram Webhook updates.
    Ensures idempotency, secret token verification, and atomic processing.
    """
    if config.WEBHOOK_SECRET and secret_token != config.WEBHOOK_SECRET:
        return {"status": "error", "message": "Unauthorized secret token"}

    update_id = update_data.get("update_id")
    if update_id is not None:
        conn = await get_db_connection()
        try:
            # Check idempotency
            async with conn.execute("SELECT update_id FROM processed_updates WHERE update_id = ?", (update_id,)) as cur:
                if await cur.fetchone():
                    logger.info(f"Duplicate update {update_id} dropped.")
                    return {"status": "ok", "message": "Duplicate skipped"}

            await conn.execute("INSERT INTO processed_updates (update_id) VALUES (?)", (update_id,))
            await conn.commit()
        finally:
            await conn.close()

    try:
        telegram_update = Update.model_validate(update_data, context={"bot": bot})
        await dp.feed_update(bot=bot, update=telegram_update)
        return {"status": "ok"}
    except Exception as e:
        logger.error(f"Error processing update: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}

# ASGI Application for serverless deployment (Lambda / Vercel / Cloud Run / FastAPI)
async def asgi_app(scope, receive, send):
    if scope["type"] == "lifespan":
        while True:
            message = await receive()
            if message["type"] == "lifespan.startup":
                await init_db()
                await send({"type": "lifespan.startup.complete"})
            elif message["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return

    if scope["type"] == "http":
        headers = dict(scope.get("headers", []))
        secret_header = headers.get(b"x-telegram-bot-api-secret-token", b"").decode("utf-8")

        # Read body
        body = bytearray()
        while True:
            msg = await receive()
            body.extend(msg.get("body", b""))
            if not msg.get("more_body", False):
                break

        if scope["method"] == "GET" and scope["path"] == "/health":
            resp_bytes = b'{"status": "healthy", "service": "PokePlay Serverless Bot"}'
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")]
            })
            await send({"type": "http.response.body", "body": resp_bytes})
            return

        try:
            update_json = json.loads(body.decode("utf-8")) if body else {}
        except Exception:
            update_json = {}

        result = await process_telegram_update(update_json, secret_token=secret_header)
        status_code = 200 if result.get("status") == "ok" else 403
        resp_data = json.dumps(result).encode("utf-8")

        await send({
            "type": "http.response.start",
            "status": status_code,
            "headers": [(b"content-type", b"application/json")]
        })
        await send({"type": "http.response.body", "body": resp_data})

app = asgi_app
