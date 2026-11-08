from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.services.user_service import get_user
from src.services.iv_engine import calculate_iv_percentage
from src.db.connection import get_db_connection

router = Router()
PAGE_SIZE = 10

async def render_pokemon_list(user_id: int, page: int = 1, sort_by: str = "id_desc") -> tuple[str, InlineKeyboardMarkup]:
    conn = await get_db_connection()
    try:
        # Count total
        async with conn.execute("SELECT COUNT(*) FROM user_pokemon WHERE user_id = ?", (user_id,)) as cur:
            total_count = (await cur.fetchone())[0]

        total_pages = max(1, (total_count + PAGE_SIZE - 1) // PAGE_SIZE)
        page = max(1, min(page, total_pages))
        offset = (page - 1) * PAGE_SIZE

        # Sort query
        order_clause = "id DESC"
        if sort_by == "iv_desc":
            order_clause = "(iv_hp + iv_atk + iv_def + iv_spa + iv_spd + iv_spe) DESC"
        elif sort_by == "level_desc":
            order_clause = "level DESC"
        elif sort_by == "name_asc":
            order_clause = "species_name ASC"

        async with conn.execute(
            f"SELECT * FROM user_pokemon WHERE user_id = ? ORDER BY {order_clause} LIMIT ? OFFSET ?",
            (user_id, PAGE_SIZE, offset)
        ) as cur:
            pokes = await cur.fetchall()
    finally:
        await conn.close()

    user = await get_user(user_id)
    text = (
        f"🐾 <b>{user['first_name']}'s Pokémon Collection</b>\n"
        f"Total: <b>{total_count}</b> Pokémon | Page <b>{page}/{total_pages}</b>\n\n"
    )

    if not pokes:
        text += "<i>You don't own any Pokémon yet! Go /hunt or claim a starter in /start.</i>\n"
    else:
        for p in pokes:
            ivs = {
                "hp": p["iv_hp"], "atk": p["iv_atk"], "def": p["iv_def"],
                "spa": p["iv_spa"], "spd": p["iv_spd"], "spe": p["iv_spe"]
            }
            iv_pct = calculate_iv_percentage(ivs)
            shiny_icon = "✨" if p["is_shiny"] else ""
            gender_icon = "♂" if p["gender"] == "male" else ("♀" if p["gender"] == "female" else "⚪")
            text += (
                f"• <b>#{p['id']}</b> {shiny_icon}<b>{p['species_name']}</b> {gender_icon} (Lv. {p['level']})\n"
                f"  └ IVs: <b>{iv_pct}%</b> | Nature: <i>{p['nature']}</i>\n"
            )

    # Navigation buttons
    nav_row = []
    if page > 1:
        nav_row.append(InlineKeyboardButton(text="◀ Prev", callback_data=f"poke_page:{page-1}:{sort_by}:{user_id}"))
    nav_row.append(InlineKeyboardButton(text=f"📄 {page}/{total_pages}", callback_data=f"poke_noop:{user_id}"))
    if page < total_pages:
        nav_row.append(InlineKeyboardButton(text="Next ▶", callback_data=f"poke_page:{page+1}:{sort_by}:{user_id}"))

    sort_row = [
        InlineKeyboardButton(text="⚡ Sort IV", callback_data=f"poke_page:1:iv_desc:{user_id}"),
        InlineKeyboardButton(text="📈 Sort Level", callback_data=f"poke_page:1:level_desc:{user_id}"),
        InlineKeyboardButton(text="🕒 Recent", callback_data=f"poke_page:1:id_desc:{user_id}")
    ]
    menu_row = [InlineKeyboardButton(text="🔙 Main Menu", callback_data="menu_main")]

    keyboard = InlineKeyboardMarkup(inline_keyboard=[nav_row, sort_row, menu_row])
    return text, keyboard

@router.message(F.text.startswith("/mypokemon") | F.text.startswith("/mypokemons"))
async def handle_mypokemon(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not user:
        await message.answer("⚠️ You haven't registered yet! Use /start to begin.")
        return

    text, kb = await render_pokemon_list(user_id, page=1, sort_by="id_desc")
    await message.answer(text, reply_markup=kb)

@router.callback_query(F.data.startswith("poke_page:"))
async def handle_pokemon_page(query: CallbackQuery):
    parts = query.data.split(":")
    page = int(parts[1])
    sort_by = parts[2]
    owner_id = int(parts[3])

    if query.from_user.id != owner_id:
        await query.answer("⚠️ Not your Pokémon box!", show_alert=True)
        return

    text, kb = await render_pokemon_list(owner_id, page=page, sort_by=sort_by)
    await query.message.edit_text(text, reply_markup=kb)
    await query.answer()

@router.callback_query(F.data.startswith("poke_noop:"))
async def handle_poke_noop(query: CallbackQuery):
    await query.answer("Page indicator")

@router.callback_query(F.data == "menu_mypokemon")
async def handle_mypokemon_menu(query: CallbackQuery):
    user_id = query.from_user.id
    user = await get_user(user_id)
    if not user:
        await query.answer("Please type /start first.", show_alert=True)
        return

    text, kb = await render_pokemon_list(user_id, page=1, sort_by="id_desc")
    await query.message.edit_text(text, reply_markup=kb)
    await query.answer()
