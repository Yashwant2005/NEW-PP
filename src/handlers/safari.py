from datetime import datetime, timedelta
from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.services.user_service import get_user
from src.services.spawn_engine import generate_encounter
from src.handlers.hunt import get_catch_keyboard
from src.db.connection import get_db_connection

router = Router()

SAFARI_REGIONS = ["kanto", "johto", "hoenn", "sinnoh", "unova", "kalos", "alola", "galar", "hisui", "paldea"]

async def get_active_safari_session(user_id: int):
    conn = await get_db_connection()
    try:
        async with conn.execute("SELECT * FROM safari_sessions WHERE user_id = ? AND is_active = 1", (user_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None
    finally:
        await conn.close()

def get_safari_menu_keyboard(user_id: int, has_session: bool) -> InlineKeyboardMarkup:
    if has_session:
        return InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Hunt in Safari Zone", callback_data=f"safari:hunt:{user_id}")],
            [InlineKeyboardButton(text="🚪 Exit Safari Zone", callback_data=f"safari:exit:{user_id}")],
            [InlineKeyboardButton(text="🔙 Main Menu", callback_data="menu_main")]
        ])
    else:
        # Zone selection buttons
        rows = [
            [
                InlineKeyboardButton(text="🏞️ Kanto", callback_data=f"safari:enter:kanto:{user_id}"),
                InlineKeyboardButton(text="🏞️ Johto", callback_data=f"safari:enter:johto:{user_id}"),
                InlineKeyboardButton(text="🏞️ Hoenn", callback_data=f"safari:enter:hoenn:{user_id}")
            ],
            [
                InlineKeyboardButton(text="🎟️ Claim Daily Safari Pass", callback_data=f"safari:claim:{user_id}")
            ],
            [
                InlineKeyboardButton(text="🔙 Main Menu", callback_data="menu_main")
            ]
        ]
        return InlineKeyboardMarkup(inline_keyboard=rows)

@router.message(F.text.startswith("/safari_zone") | F.text.startswith("/safari"))
async def handle_safari_zone(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not user:
        await message.answer("⚠️ You haven't registered yet! Use /start to begin.")
        return

    session = await get_active_safari_session(user_id)
    if session:
        conn = await get_db_connection()
        try:
            async with conn.execute("SELECT quantity FROM user_inventory WHERE user_id = ? AND item_id = 'safari'", (user_id,)) as cur:
                balls = (await cur.fetchone())["quantity"]
        finally:
            await conn.close()

        text = (
            f"🏞️ <b>Safari Zone — {session['zone'].capitalize()}</b>\n\n"
            f"🟢 <b>Safari Balls Remaining:</b> {balls}/30\n"
            f"🕒 <b>Session Started:</b> {session['started_at'][:19]}\n\n"
            "Encounter rare and exotic Pokémon with boosted shiny rates!\n"
            "Ready to explore?"
        )
        kb = get_safari_menu_keyboard(user_id, has_session=True)
    else:
        text = (
            "🏞️ <b>Welcome to the Pokémon Safari Zone!</b> 🏞️\n\n"
            "The Safari Zone is a special reserve teeming with rare, exotic, and legendary species.\n\n"
            "<b>Safari Rules:</b>\n"
            "• Each entry grants <b>30 Safari Balls</b> (3x catch multiplier)\n"
            "• Pokémon can flee at any time if catch fails\n"
            "• Claim <b>1 Free Safari Pass</b> every day\n\n"
            f"🎟️ <b>Your Safari Passes:</b> {user['safari_passes']}\n\n"
            "Select a zone to enter or claim your daily pass:"
        )
        kb = get_safari_menu_keyboard(user_id, has_session=False)

    await message.answer(text, reply_markup=kb)

@router.message(F.text.startswith("/claim_safari_pass"))
async def handle_claim_safari_pass(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not user:
        await message.answer("⚠️ Please /start first.")
        return

    conn = await get_db_connection()
    try:
        async with conn.execute("SELECT expires_at FROM cooldowns WHERE user_id = ? AND action = 'daily_safari_pass'", (user_id,)) as cur:
            row = await cur.fetchone()
            if row:
                expires_at = datetime.fromisoformat(row["expires_at"]) if isinstance(row["expires_at"], str) else row["expires_at"]
                if expires_at > datetime.utcnow():
                    rem = int((expires_at - datetime.utcnow()).total_seconds())
                    hours, rem = divmod(rem, 3600)
                    mins, _ = divmod(rem, 60)
                    await message.answer(f"⏳ You have already claimed your daily pass today! Next claim available in <b>{hours}h {mins}m</b>.")
                    return

        # Grant 1 pass and reset cooldown to UTC midnight
        now = datetime.utcnow()
        midnight = datetime(now.year, now.month, now.day) + timedelta(days=1)

        await conn.execute("UPDATE users SET safari_passes = safari_passes + 1 WHERE telegram_id = ?", (user_id,))
        await conn.execute(
            """
            INSERT INTO cooldowns (user_id, action, expires_at) VALUES (?, 'daily_safari_pass', ?)
            ON CONFLICT(user_id, action) DO UPDATE SET expires_at = excluded.expires_at
            """,
            (user_id, midnight.isoformat())
        )
        await conn.commit()
    finally:
        await conn.close()

    await message.answer("🎉 <b>Daily Safari Pass Claimed!</b> 🎟️\n\nYou received 1 Safari Pass. Head into /safari_zone to start hunting!")

@router.message(F.text.startswith("/enter"))
async def handle_enter_cmd(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not user:
        await message.answer("⚠️ Please /start first.")
        return

    session = await get_active_safari_session(user_id)
    if session:
        await message.answer(f"⚠️ You are already inside the <b>{session['zone'].capitalize()} Safari Zone</b>! Use /safari to continue.")
        return

    if user["safari_passes"] <= 0:
        await message.answer("⚠️ You don't have any Safari Passes! Use /claim_safari_pass to get a free daily pass.")
        return

    # Enter Kanto by default if not specified
    zone = "kanto"
    parts = message.text.split()
    if len(parts) > 1 and parts[1].lower() in SAFARI_REGIONS:
        zone = parts[1].lower()

    conn = await get_db_connection()
    try:
        await conn.execute("UPDATE users SET safari_passes = safari_passes - 1 WHERE telegram_id = ?", (user_id,))
        await conn.execute(
            """
            INSERT INTO safari_sessions (user_id, zone, balls_left, is_active)
            VALUES (?, ?, 30, 1)
            ON CONFLICT(user_id) DO UPDATE SET zone=excluded.zone, balls_left=30, is_active=1, started_at=CURRENT_TIMESTAMP
            """,
            (user_id, zone)
        )
        await conn.execute(
            """
            INSERT INTO user_inventory (user_id, item_id, item_type, quantity)
            VALUES (?, 'safari', 'ball', 30)
            ON CONFLICT(user_id, item_id) DO UPDATE SET quantity = 30
            """,
            (user_id,)
        )
        await conn.commit()
    finally:
        await conn.close()

    await message.answer(
        f"🌲 <b>Welcome to the {zone.capitalize()} Safari Zone!</b> 🌲\n\n"
        "You were equipped with <b>30 Safari Balls</b>.\n"
        "Tap the button below to start hunting exotic Pokémon!",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🎯 Hunt in Safari Zone", callback_data=f"safari:hunt:{user_id}")],
            [InlineKeyboardButton(text="🚪 Exit Safari", callback_data=f"safari:exit:{user_id}")]
        ])
    )

@router.message(F.text.startswith("/exit"))
async def handle_exit_cmd(message: Message):
    user_id = message.from_user.id
    conn = await get_db_connection()
    try:
        await conn.execute("UPDATE safari_sessions SET is_active = 0 WHERE user_id = ?", (user_id,))
        await conn.execute("UPDATE user_inventory SET quantity = 0 WHERE user_id = ? AND item_id = 'safari'", (user_id,))
        await conn.commit()
    finally:
        await conn.close()
    await message.answer("🚪 You exited the Safari Zone safely. Remaining Safari Balls have been returned.")

@router.callback_query(F.data.startswith("safari:"))
async def handle_safari_callbacks(query: CallbackQuery):
    parts = query.data.split(":")
    action = parts[1]

    if action == "enter":
        zone = parts[2]
        owner_id = int(parts[3])
        if query.from_user.id != owner_id:
            await query.answer("⚠️ Not your menu!", show_alert=True)
            return

        user = await get_user(owner_id)
        if user["safari_passes"] <= 0:
            await query.answer("⚠️ No Safari Passes left! Claim your daily pass first.", show_alert=True)
            return

        conn = await get_db_connection()
        try:
            await conn.execute("UPDATE users SET safari_passes = safari_passes - 1 WHERE telegram_id = ?", (owner_id,))
            await conn.execute(
                """
                INSERT INTO safari_sessions (user_id, zone, balls_left, is_active)
                VALUES (?, ?, 30, 1)
                ON CONFLICT(user_id) DO UPDATE SET zone=excluded.zone, balls_left=30, is_active=1, started_at=CURRENT_TIMESTAMP
                """,
                (owner_id, zone)
            )
            await conn.execute(
                """
                INSERT INTO user_inventory (user_id, item_id, item_type, quantity)
                VALUES (?, 'safari', 'ball', 30)
                ON CONFLICT(user_id, item_id) DO UPDATE SET quantity = 30
                """,
                (owner_id,)
            )
            await conn.commit()
        finally:
            await conn.close()

        await query.message.edit_text(
            f"🌲 <b>Welcome to the {zone.capitalize()} Safari Zone!</b> 🌲\n\n"
            "You were granted <b>30 Safari Balls</b>.\n"
            "Begin your safari expedition:",
            reply_markup=get_safari_menu_keyboard(owner_id, has_session=True)
        )
        await query.answer("Entered Safari Zone!")

    elif action == "hunt":
        owner_id = int(parts[2])
        if query.from_user.id != owner_id:
            await query.answer("⚠️ Not your menu!", show_alert=True)
            return

        session = await get_active_safari_session(owner_id)
        if not session:
            await query.answer("⚠️ You are not in an active Safari session!", show_alert=True)
            return

        conn = await get_db_connection()
        try:
            async with conn.execute("SELECT quantity FROM user_inventory WHERE user_id = ? AND item_id = 'safari'", (owner_id,)) as cur:
                balls_left = (await cur.fetchone())["quantity"]
        finally:
            await conn.close()

        if balls_left <= 0:
            await query.message.edit_text(
                "⚠️ <b>Out of Safari Balls!</b>\n\nYour Safari session has concluded.",
                reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                    [InlineKeyboardButton(text="🚪 Exit Safari", callback_data=f"safari:exit:{owner_id}")]
                ])
            )
            await query.answer("Out of balls!")
            return

        encounter = await generate_encounter(owner_id, region=session["zone"], is_safari=True)
        shiny_tag = "✨ <b>SAFARI SHINY!</b> " if encounter["is_shiny"] else ""
        text = (
            f"🏞️ <b>Safari Encounter!</b> 🏞️\n\n"
            f"{shiny_tag}<b>{encounter['species_name']}</b> (Lv. {encounter['level']})\n"
            f"🟢 <b>Safari Balls Left:</b> {balls_left}\n"
            f"🎭 <b>Nature:</b> {encounter['nature']} | 🎯 <b>Catch Rate:</b> {encounter['catch_rate']}\n\n"
            "Throw a Safari Ball or flee:"
        )
        kb = await get_catch_keyboard(owner_id, encounter["encounter_id"], is_safari=True)
        await query.message.edit_text(text, reply_markup=kb)
        await query.answer()

    elif action == "exit":
        owner_id = int(parts[2])
        if query.from_user.id != owner_id:
            await query.answer("⚠️ Not your menu!", show_alert=True)
            return

        conn = await get_db_connection()
        try:
            await conn.execute("UPDATE safari_sessions SET is_active = 0 WHERE user_id = ?", (owner_id,))
            await conn.execute("UPDATE user_inventory SET quantity = 0 WHERE user_id = ? AND item_id = 'safari'", (owner_id,))
            await conn.commit()
        finally:
            await conn.close()

        await query.message.edit_text(
            "🚪 <b>You exited the Safari Zone.</b>\n\nThanks for exploring! Come back tomorrow for another daily pass.",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[
                [InlineKeyboardButton(text="🔙 Main Menu", callback_data="menu_main")]
            ])
        )
        await query.answer("Exited Safari!")

    elif action == "claim":
        owner_id = int(parts[2])
        if query.from_user.id != owner_id:
            await query.answer("⚠️ Not your menu!", show_alert=True)
            return

        conn = await get_db_connection()
        try:
            async with conn.execute("SELECT expires_at FROM cooldowns WHERE user_id = ? AND action = 'daily_safari_pass'", (owner_id,)) as cur:
                row = await cur.fetchone()
                if row:
                    expires_at = datetime.fromisoformat(row["expires_at"]) if isinstance(row["expires_at"], str) else row["expires_at"]
                    if expires_at > datetime.utcnow():
                        rem = int((expires_at - datetime.utcnow()).total_seconds())
                        hours, rem = divmod(rem, 3600)
                        mins, _ = divmod(rem, 60)
                        await query.answer(f"Already claimed today! Next in {hours}h {mins}m.", show_alert=True)
                        return

            now = datetime.utcnow()
            midnight = datetime(now.year, now.month, now.day) + timedelta(days=1)
            await conn.execute("UPDATE users SET safari_passes = safari_passes + 1 WHERE telegram_id = ?", (owner_id,))
            await conn.execute(
                """
                INSERT INTO cooldowns (user_id, action, expires_at) VALUES (?, 'daily_safari_pass', ?)
                ON CONFLICT(user_id, action) DO UPDATE SET expires_at = excluded.expires_at
                """,
                (owner_id, midnight.isoformat())
            )
            await conn.commit()
        finally:
            await conn.close()

        user = await get_user(owner_id)
        await query.message.edit_text(
            f"🎉 <b>1 Free Safari Pass Claimed!</b> 🎟️\n\n"
            f"You now hold <b>{user['safari_passes']}</b> Safari Passes.",
            reply_markup=get_safari_menu_keyboard(owner_id, has_session=False)
        )
        await query.answer("Pass claimed!")

@router.callback_query(F.data == "menu_safari")
async def handle_safari_menu(query: CallbackQuery):
    user_id = query.from_user.id
    user = await get_user(user_id)
    if not user:
        await query.answer("Please type /start first.", show_alert=True)
        return

    session = await get_active_safari_session(user_id)
    text = (
        "🏞️ <b>Safari Zone Headquarters</b> 🏞️\n\n"
        f"🎟️ <b>Available Passes:</b> {user['safari_passes']}\n\n"
        "Choose an action:"
    )
    kb = get_safari_menu_keyboard(user_id, has_session=bool(session))
    await query.message.edit_text(text, reply_markup=kb)
    await query.answer()
