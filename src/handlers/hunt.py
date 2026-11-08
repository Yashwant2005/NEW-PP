import json
from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.services.user_service import get_user
from src.services.spawn_engine import generate_encounter, get_active_encounter
from src.services.catch_engine import attempt_catch
from src.services.iv_engine import calculate_iv_percentage
from src.db.connection import get_db_connection

router = Router()

def format_catch_rate(cr) -> str:
    if isinstance(cr, dict):
        val = cr.get("value", 45)
        pct = cr.get("percentage")
        if pct is not None:
            return f"{val} ({pct:.1f}%)"
        return str(val)
    return str(cr)

async def check_hunt_cooldown(user_id: int) -> int:
    conn = await get_db_connection()
    try:
        async with conn.execute(
            "SELECT expires_at FROM cooldowns WHERE user_id = ? AND action = 'hunt'",
            (user_id,)
        ) as cur:
            row = await cur.fetchone()
            if row:
                expires_at = datetime.fromisoformat(row["expires_at"]) if isinstance(row["expires_at"], str) else row["expires_at"]
                remaining = (expires_at - datetime.utcnow()).total_seconds()
                if remaining > 0:
                    return int(remaining)
        return 0
    finally:
        await conn.close()

async def set_hunt_cooldown(user_id: int, seconds: int = 5):
    expires_at = datetime.utcnow() + timedelta(seconds=seconds)
    conn = await get_db_connection()
    try:
        await conn.execute(
            """
            INSERT INTO cooldowns (user_id, action, expires_at)
            VALUES (?, 'hunt', ?)
            ON CONFLICT(user_id, action) DO UPDATE SET expires_at = excluded.expires_at
            """,
            (user_id, expires_at.isoformat())
        )
        await conn.commit()
    finally:
        await conn.close()

async def get_catch_keyboard(user_id: int, encounter_id: str, is_safari: bool = False) -> InlineKeyboardMarkup:
    conn = await get_db_connection()
    try:
        async with conn.execute(
            "SELECT item_id, quantity FROM user_inventory WHERE user_id = ? AND item_type = 'ball'",
            (user_id,)
        ) as cur:
            balls = {row["item_id"]: row["quantity"] for row in await cur.fetchall()}
    finally:
        await conn.close()

    rows = []
    if is_safari:
        safari_count = balls.get("safari", 0)
        rows.append([
            InlineKeyboardButton(text=f"🟢 Throw Safari Ball (x{safari_count})", callback_data=f"throw:{encounter_id}:safari:{user_id}")
        ])
    else:
        rows.append([
            InlineKeyboardButton(text=f"⚾ Regular (x{balls.get('regular', 0)})", callback_data=f"throw:{encounter_id}:regular:{user_id}"),
            InlineKeyboardButton(text=f"🔵 Great (x{balls.get('great', 0)})", callback_data=f"throw:{encounter_id}:great:{user_id}")
        ])
        rows.append([
            InlineKeyboardButton(text=f"⚫ Ultra (x{balls.get('ultra', 0)})", callback_data=f"throw:{encounter_id}:ultra:{user_id}"),
            InlineKeyboardButton(text=f"🟣 Master (x{balls.get('master', 0)})", callback_data=f"throw:{encounter_id}:master:{user_id}")
        ])

    rows.append([
        InlineKeyboardButton(text="🏃 Run Away", callback_data=f"run:{encounter_id}:{user_id}")
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)

async def start_hunt_flow(user_id: int, send_fn):
    user = await get_user(user_id)
    if not user:
        await send_fn("⚠️ You must start your journey first! Type /start to register.")
        return

    cooldown = await check_hunt_cooldown(user_id)
    if cooldown > 0:
        await send_fn(f"⏳ Please wait <b>{cooldown}s</b> before hunting again!")
        return

    await set_hunt_cooldown(user_id, seconds=5)
    encounter = await generate_encounter(user_id, region=user["selected_region"], is_safari=False)

    shiny_str = "✨ <b>SHINY!</b> " if encounter["is_shiny"] else ""
    catch_rate_str = format_catch_rate(encounter["catch_rate"])
    text = (
        f"🌲 <b>A Wild Pokémon Appeared!</b> 🌲\n\n"
        f"{shiny_str}<b>{encounter['species_name']}</b> (Lv. {encounter['level']})\n"
        f"⚧ <b>Gender:</b> {encounter['gender'].capitalize()} | 🎭 <b>Nature:</b> {encounter['nature']}\n"
        f"🎯 <b>Catch Rate:</b> {catch_rate_str}\n\n"
        "Choose a Poké Ball to throw or run away:"
    )

    kb = await get_catch_keyboard(user_id, encounter["encounter_id"], is_safari=False)
    await send_fn(text, reply_markup=kb)

@router.message(F.text.startswith("/hunt"))
async def handle_hunt(message: Message):
    await start_hunt_flow(message.from_user.id, message.answer)

@router.callback_query(F.data == "menu_hunt")
async def handle_menu_hunt(query: CallbackQuery):
    await query.answer()
    await start_hunt_flow(query.from_user.id, query.message.answer)

@router.callback_query(F.data.startswith("throw:"))
async def handle_throw_ball(query: CallbackQuery):
    parts = query.data.split(":")
    encounter_id = parts[1]
    ball_type = parts[2]
    owner_id = int(parts[3])

    if query.from_user.id != owner_id:
        await query.answer("⚠️ This encounter is not yours!", show_alert=True)
        return

    encounter = await get_active_encounter(encounter_id)
    if not encounter:
        await query.answer("⚠️ This encounter has ended or expired.", show_alert=True)
        await query.message.edit_text("💨 The Pokémon is no longer here.")
        return

    success, result_message = await attempt_catch(owner_id, encounter, ball_type)

    if success:
        iv_pct = calculate_iv_percentage(encounter["ivs"])
        shiny_tag = "✨ Shiny " if encounter.get("is_shiny") else ""
        text = (
            f"🎉 <b>SUCCESS!</b> 🎉\n\n"
            f"You caught a {shiny_tag}<b>{encounter['species_name']}</b>!\n"
            f"📊 <b>Level:</b> {encounter['level']} | 📈 <b>IVs:</b> {iv_pct}%\n"
            f"🎭 <b>Nature:</b> {encounter['nature']} | ⚧ <b>Gender:</b> {encounter['gender'].capitalize()}\n\n"
            f"{result_message}\n\n"
            "View it anytime in /mypokemon!"
        )
        await query.message.edit_text(text)
        await query.answer("Caught!")
    else:
        if "fled" in result_message:
            await query.message.edit_text(result_message)
            await query.answer("Fled!")
        else:
            kb = await get_catch_keyboard(owner_id, encounter_id, is_safari=bool(encounter.get("is_safari")))
            await query.message.edit_text(
                f"🌲 <b>Wild {encounter['species_name']} (Lv. {encounter['level']})</b>\n\n"
                f"{result_message}\n\n"
                "Try again:",
                reply_markup=kb
            )
            await query.answer("Catch missed!")

@router.callback_query(F.data.startswith("run:"))
async def handle_run(query: CallbackQuery):
    parts = query.data.split(":")
    encounter_id = parts[1]
    owner_id = int(parts[2])

    if query.from_user.id != owner_id:
        await query.answer("⚠️ Not your encounter!", show_alert=True)
        return

    conn = await get_db_connection()
    try:
        await conn.execute("UPDATE encounters SET status = 'fled' WHERE encounter_id = ?", (encounter_id,))
        await conn.commit()
    finally:
        await conn.close()

    await query.message.edit_text("🏃 You got away safely!")
    await query.answer("Ran away!")
