import logging
import asyncio
import aiohttp
from aiohttp import web

from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

API_TOKEN = "7732017441:AAEBr-MUe_1MpdE3Ahpv5CAXwDxEYRMvYyA"
ADMIN_ID = 7339714216  # <-- o'zgartiring

# Google Apps Script URL
API_URL = "https://script.google.com/macros/s/AKfycbzffXKXTzbGARB68yt9h65hVvI9f9qRmz89ZR-ilmhOCSB2F1AeRWvGpfPuhQ8apE7niA/exec"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

# ================= FSM =================
class AddChannel(StatesGroup):
    waiting_forward = State()

class AdState(StatesGroup):
    selecting_channels = State()
    waiting_content = State()

# ================= MENU =================
def main_menu(user_id):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("➕ Kanal qo'shish"))
    kb.add(KeyboardButton("📢 Reklama yuborish"))
    if user_id == ADMIN_ID:
        kb.add(KeyboardButton("📊 Statistika"))
    return kb

# ================= API =================
async def get_channels(user_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}?action=get&user_id={user_id}") as resp:
            return await resp.json()

async def add_channel(user_id, channel_id, title):
    async with aiohttp.ClientSession() as session:
        await session.get(
            f"{API_URL}?action=add&user_id={user_id}&channel_id={channel_id}&title={title}"
        )

# ================= START =================
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    await msg.answer("👋 Salom!\nProfessional Ads Manager Botga xush kelibsiz!",
                     reply_markup=main_menu(msg.from_user.id))

# ================= ADD CHANNEL =================
@dp.message_handler(lambda m: m.text == "➕ Kanal qo'shish")
async def add_channel_start(msg: types.Message):
    await msg.answer("📩 Kanal postidan *forward* qilib yuboring")
    await AddChannel.waiting_forward.set()

@dp.message_handler(state=AddChannel.waiting_forward, content_types=types.ContentType.ANY)
async def save_channel(msg: types.Message, state: FSMContext):
    if not msg.forward_from_chat:
        return await msg.answer("❌ Faqat kanal postini forward qiling")

    chat = msg.forward_from_chat

    await add_channel(msg.from_user.id, chat.id, chat.title)

    await msg.answer(f"✅ Kanal qo'shildi:\n{chat.title}")
    await state.finish()

# ================= INLINE KEYBOARD =================
def build_channels_keyboard(channels, selected):
    kb = InlineKeyboardMarkup()
    for ch in channels:
        cid = str(ch['channel_id'])
        title = ch['title']

        icon = "🟢" if cid in selected else "⚪"

        kb.add(InlineKeyboardButton(
            f"{icon} {title}",
            callback_data=f"toggle:{cid}"
        ))

    kb.add(InlineKeyboardButton("✅ Tanladim", callback_data="done"))
    return kb

# ================= ADS =================
@dp.message_handler(lambda m: m.text == "📢 Reklama yuborish")
async def ads_start(msg: types.Message, state: FSMContext):
    user_id = msg.from_user.id

    if user_id == ADMIN_ID:
        channels = await get_channels("all")
    else:
        channels = await get_channels(user_id)

    await state.update_data(
        channels=channels,
        selected=[]
    )

    await msg.answer(
        "📌 Kanallarni tanlang:",
        reply_markup=build_channels_keyboard(channels, [])
    )

    await AdState.selecting_channels.set()

# ================= TOGGLE =================
@dp.callback_query_handler(lambda c: c.data.startswith("toggle"), state=AdState.selecting_channels)
async def toggle_channel(call: types.CallbackQuery, state: FSMContext):
    cid = call.data.split(":")[1]

    data = await state.get_data()
    selected = data.get("selected", [])
    channels = data.get("channels", [])

    if cid in selected:
        selected.remove(cid)
    else:
        selected.append(cid)

    await state.update_data(selected=selected)

    await call.message.edit_reply_markup(
        reply_markup=build_channels_keyboard(channels, selected)
    )

    await call.answer()

# ================= DONE =================
@dp.callback_query_handler(lambda c: c.data == "done", state=AdState.selecting_channels)
async def done_select(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected", [])

    if not selected:
        return await call.answer("❗ Hech narsa tanlanmadi", show_alert=True)

    await call.message.answer("📩 Endi reklama kontentini yuboring (text/photo/video)")
    await AdState.waiting_content.set()

# ================= SEND ADS =================
@dp.message_handler(state=AdState.waiting_content, content_types=types.ContentType.ANY)
async def send_ads(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected", [])

    success = 0

    for cid in selected:
        try:
            await msg.send_copy(chat_id=int(cid))
            success += 1
        except Exception as e:
            print("ERROR:", e)

    await msg.answer(f"✅ Yuborildi: {success} ta kanalga")

    await state.finish()

# ================= WEB SERVER =================
async def handle(request):
    return web.Response(text="Bot is running")

async def start_web_app():
    app = web.Application()
    app.router.add_get('/', handle)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()

# ================= MAIN =================
async def on_startup(dp):
    asyncio.create_task(start_web_app())
    print("🚀 Bot ishga tushdi")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
