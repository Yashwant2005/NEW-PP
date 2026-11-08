from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.services.user_service import get_user
from src.db.connection import get_db_connection

router = Router()

CATEGORY_EMOJIS = {
    "ball": "⚾",
    "stone": "💎",
    "candy": "🍬",
    "medicine": "🧪",
    "key": "🔑"
}

async def render_bag(user_id: int, category: str = "all") -> tuple[str, InlineKeyboardMarkup]:
    user = await get_user(user_id)
    conn = await get_db_connection()
    try:
        if category == "all":
            async with conn.execute(
                "SELECT item_id, item_type, quantity FROM user_inventory WHERE user_id = ? AND quantity > 0 ORDER BY item_type, item_id",
                (user_id,)
            ) as cur:
                items = await cur.fetchall()
        else:
            async with conn.execute(
                "SELECT item_id, item_type, quantity FROM user_inventory WHERE user_id = ? AND item_type = ? AND quantity > 0 ORDER BY item_id",
                (user_id, category)
            ) as cur:
                items = await cur.fetchall()
    finally:
        await conn.close()

    text = (
        f"🎒 <b>{user['first_name']}'s Adventure Bag</b>\n\n"
        f"💰 <b>PokéCoins:</b> {user['coins']:,} 🪙\n"
        f"🏆 <b>League Points:</b> {user['league_points']:,} LP\n"
        f"🎫 <b>Safari Passes:</b> {user['safari_passes']} 🎟️\n\n"
        f"<b>── Inventory Items ({category.capitalize()}) ──</b>\n"
    )

    if not items:
        text += "<i>Your bag is currently empty in this category!</i>\n"
    else:
        for it in items:
            emoji = CATEGORY_EMOJIS.get(it["item_type"], "📦")
            name = it["item_id"].replace("_", " ").title()
            text += f"{emoji} <b>{name}</b> x{it['quantity']}\n"

    # Category filter keyboard
    buttons = [
        [
            InlineKeyboardButton(text="📦 All", callback_data=f"bag:all:{user_id}"),
            InlineKeyboardButton(text="⚾ Balls", callback_data=f"bag:ball:{user_id}"),
            InlineKeyboardButton(text="💎 Stones", callback_data=f"bag:stone:{user_id}")
        ],
        [
            InlineKeyboardButton(text="🍬 Candies", callback_data=f"bag:candy:{user_id}"),
            InlineKeyboardButton(text="🧪 Medicine", callback_data=f"bag:medicine:{user_id}")
        ],
        [
            InlineKeyboardButton(text="🔙 Main Menu", callback_data="menu_main")
        ]
    ]
    return text, InlineKeyboardMarkup(inline_keyboard=buttons)

@router.message(F.text.startswith("/mybag"))
async def handle_mybag(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)
    if not user:
        await message.answer("⚠️ You haven't registered yet! Use /start to begin.")
        return

    text, kb = await render_bag(user_id, category="all")
    await message.answer(text, reply_markup=kb)

@router.callback_query(F.data.startswith("bag:"))
async def handle_bag_filter(query: CallbackQuery):
    parts = query.data.split(":")
    category = parts[1]
    owner_id = int(parts[2])

    if query.from_user.id != owner_id:
        await query.answer("⚠️ Not your bag!", show_alert=True)
        return

    text, kb = await render_bag(owner_id, category=category)
    await query.message.edit_text(text, reply_markup=kb)
    await query.answer()

@router.callback_query(F.data == "menu_bag")
async def handle_bag_menu(query: CallbackQuery):
    user_id = query.from_user.id
    user = await get_user(user_id)
    if not user:
        await query.answer("Please type /start first.", show_alert=True)
        return

    text, kb = await render_bag(user_id, category="all")
    await query.message.edit_text(text, reply_markup=kb)
    await query.answer()
