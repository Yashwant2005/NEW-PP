from aiogram import Router, F
from aiogram.types import Message, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton
from src.services.user_service import get_user, create_user, give_starter_pokemon
from src.db.connection import get_db_connection

router = Router()

def get_main_menu_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🎯 Hunt Pokémon", callback_data="menu_hunt"),
            InlineKeyboardButton(text="🎒 My Bag", callback_data="menu_bag")
        ],
        [
            InlineKeyboardButton(text="🐾 My Pokémon", callback_data="menu_mypokemon"),
            InlineKeyboardButton(text="🏞️ Safari Zone", callback_data="menu_safari")
        ],
        [
            InlineKeyboardButton(text="👤 Trainer Profile", callback_data="menu_profile")
        ]
    ])

def get_starter_selection_keyboard(user_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌿 Bulbasaur", callback_data=f"starter_bulbasaur_{user_id}"),
            InlineKeyboardButton(text="🔥 Charmander", callback_data=f"starter_charmander_{user_id}"),
            InlineKeyboardButton(text="💧 Squirtle", callback_data=f"starter_squirtle_{user_id}")
        ]
    ])

@router.message(F.text.startswith("/start"))
async def handle_start(message: Message):
    user_id = message.from_user.id
    user = await get_user(user_id)

    if not user:
        await message.answer(
            f"🌟 <b>Welcome to PokePlay, Trainer {message.from_user.first_name}!</b> 🌟\n\n"
            "Your journey in the Pokémon world begins today!\n"
            "To embark on your adventure, choose your trusted starter Pokémon below:\n\n"
            "🌿 <b>Bulbasaur</b> — The Seed Pokémon (Grass/Poison)\n"
            "🔥 <b>Charmander</b> — The Lizard Pokémon (Fire)\n"
            "💧 <b>Squirtle</b> — The Tiny Turtle Pokémon (Water)",
            reply_markup=get_starter_selection_keyboard(user_id)
        )
    else:
        # Returning player
        conn = await get_db_connection()
        try:
            async with conn.execute("SELECT COUNT(*) FROM user_pokemon WHERE user_id = ?", (user_id,)) as cur:
                poke_count = (await cur.fetchone())[0]
        finally:
            await conn.close()

        await message.answer(
            f"👋 <b>Welcome back, Trainer {user['first_name']}!</b>\n\n"
            f"🌍 <b>Region:</b> {user['selected_region'].capitalize()}\n"
            f"💰 <b>PokéCoins:</b> {user['coins']:,}\n"
            f"🎫 <b>Safari Passes:</b> {user['safari_passes']}\n"
            f"🐾 <b>Pokémon Owned:</b> {poke_count}\n\n"
            "What would you like to do next?",
            reply_markup=get_main_menu_keyboard()
        )

@router.callback_query(F.data.startswith("starter_"))
async def handle_starter_selection(query: CallbackQuery):
    parts = query.data.split("_")
    starter_name = parts[1]
    target_user_id = int(parts[2])

    if query.from_user.id != target_user_id:
        await query.answer("⚠️ This starter selection is not for you!", show_alert=True)
        return

    user = await get_user(target_user_id)
    if user:
        await query.answer("You already have an active profile!", show_alert=True)
        await query.message.edit_text(
            f"Welcome back, Trainer {user['first_name']}!",
            reply_markup=get_main_menu_keyboard()
        )
        return

    await create_user(
        telegram_id=target_user_id,
        username=query.from_user.username,
        first_name=query.from_user.first_name
    )
    poke = await give_starter_pokemon(target_user_id, starter_name)

    await query.message.edit_text(
        f"🎉 <b>Congratulations, Trainer {query.from_user.first_name}!</b> 🎉\n\n"
        f"You chose <b>{starter_name.capitalize()}</b> as your starter companion!\n"
        f"We've also added <b>15 Regular Balls</b>, <b>5 Great Balls</b>, <b>2 Ultra Balls</b>, and <b>1,000 PokéCoins</b> to your bag.\n\n"
        "Use the menu below to start hunting and exploring!",
        reply_markup=get_main_menu_keyboard()
    )
    await query.answer()

@router.callback_query(F.data == "menu_profile")
async def handle_profile_menu(query: CallbackQuery):
    user_id = query.from_user.id
    user = await get_user(user_id)
    if not user:
        await query.answer("User profile not found. Please type /start.", show_alert=True)
        return

    conn = await get_db_connection()
    try:
        async with conn.execute("SELECT COUNT(*) FROM user_pokemon WHERE user_id = ?", (user_id,)) as cur:
            poke_count = (await cur.fetchone())[0]
    finally:
        await conn.close()

    text = (
        f"👤 <b>Trainer Profile: {user['first_name']}</b>\n\n"
        f"🆔 <b>ID:</b> <code>{user['telegram_id']}</code>\n"
        f"🌍 <b>Current Region:</b> {user['selected_region'].capitalize()}\n"
        f"💰 <b>PokéCoins:</b> {user['coins']:,}\n"
        f"🏆 <b>League Points:</b> {user['league_points']:,}\n"
        f"🎫 <b>Safari Passes:</b> {user['safari_passes']}\n"
        f"🐾 <b>Total Pokémon Caught:</b> {poke_count}\n"
        f"📅 <b>Trainer Since:</b> {user['created_at'][:10]}"
    )

    back_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🔙 Back to Main Menu", callback_data="menu_main")]
    ])
    await query.message.edit_text(text, reply_markup=back_kb)
    await query.answer()

@router.callback_query(F.data == "menu_main")
async def handle_main_menu(query: CallbackQuery):
    user_id = query.from_user.id
    user = await get_user(user_id)
    if not user:
        await query.answer("Please type /start first.", show_alert=True)
        return

    await query.message.edit_text(
        f"👋 <b>PokePlay Main Menu</b>\n\n"
        f"Trainer: <b>{user['first_name']}</b> | Coins: <b>{user['coins']:,}</b>\n\n"
        "Choose an option below:",
        reply_markup=get_main_menu_keyboard()
    )
    await query.answer()
