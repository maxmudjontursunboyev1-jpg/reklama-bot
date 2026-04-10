import logging
import asyncio
import aiohttp
from aiohttp import web

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

# ================= CONFIG =================
API_TOKEN = "7732017441:AAEBr-MUe_1MpdE3Ahpv5CAXwDxEYRMvYyA"
ADMIN_ID = 7339714216

API_URL = "https://script.google.com/macros/s/AKfycbzffXKXTzbGARB68yt9h65hVvI9f9qRmz89ZR-ilmhOCSB2F1AeRWvGpfPuhQ8apE7niA/exec"

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

# ================= STATES =================
class AddChannel(StatesGroup):
    waiting_forward = State()

class AdState(StatesGroup):
    selecting = State()
    content = State()

# ================= SMART EMOJI =================
def smart_format(text: str):
    text_low = text.lower()
    emojis = []

    if "kino" in text_low:
        emojis.append("🎬")
    if "aksiya" in text_low:
        emojis.append("🔥")
    if "chegirma" in text_low:
        emojis.append("💸")
    if "yangilik" in text_low:
        emojis.append("🆕")

    return " ".join(emojis) + " " + text + " 🚀"

# ================= API =================
async def api_get(user_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}?action=get&user_id={user_id}") as resp:
            return await resp.json()

async def api_add(user_id, channel_id, title):
    async with aiohttp.ClientSession() as session:
        await session.get(
            f"{API_URL}?action=add&user_id={user_id}&channel_id={channel_id}&title={title}"
        )

# ================= UI =================
def main_menu(user_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add"))
    kb.add(InlineKeyboardButton("📢 Reklama yaratish", callback_data="ads"))

    if user_id == ADMIN_ID:
        kb.add(InlineKeyboardButton("📊 Statistika", callback_data="stats"))

    return kb

def channels_kb(channels, selected):
    kb = InlineKeyboardMarkup()
    for ch in channels:
        cid = str(ch["channel_id"])
        icon = "🟢" if cid in selected else "⚪"

        kb.add(InlineKeyboardButton(
            f"{icon} {ch['title']}",
            callback_data=f"toggle:{cid}"
        ))

    kb.add(InlineKeyboardButton("✅ Tanladim", callback_data="done"))
    return kb

# ================= START =================
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    await msg.answer("👋 Professional Ads Manager Bot",
                     reply_markup=main_menu(msg.from_user.id))

# ================= ADD CHANNEL =================
@dp.callback_query_handler(lambda c: c.data == "add")
async def add_start(call: types.CallbackQuery):
    await call.message.edit_text("📩 Kanal postini forward qiling")
    await AddChannel.waiting_forward.set()

@dp.message_handler(state=AddChannel.waiting_forward, content_types=types.ContentType.ANY)
async def save_channel(msg: types.Message, state: FSMContext):
    if not msg.forward_from_chat:
        return await msg.answer("❌ Faqat kanal postini forward qiling")

    chat = msg.forward_from_chat

    await api_add(msg.from_user.id, chat.id, chat.title)

    await msg.answer(f"✅ Qo'shildi: {chat.title}")
    await state.finish()

# ================= ADS =================
@dp.callback_query_handler(lambda c: c.data == "ads")
async def ads(call: types.CallbackQuery, state: FSMContext):
    user_id = call.from_user.id

    if user_id == ADMIN_ID:
        channels = await api_get("all")
    else:
        channels = await api_get(user_id)

    await state.update_data(channels=channels, selected=[])

    await call.message.edit_text(
        "📌 Kanallarni tanlang:",
        reply_markup=channels_kb(channels, [])
    )

    await AdState.selecting.set()

# ================= TOGGLE =================
@dp.callback_query_handler(lambda c: c.data.startswith("toggle"), state=AdState.selecting)
async def toggle(call: types.CallbackQuery, state: FSMContext):
    cid = call.data.split(":")[1]

    data = await state.get_data()
    selected = set(data.get("selected", []))

    if cid in selected:
        selected.remove(cid)
    else:
        selected.add(cid)

    await state.update_data(selected=list(selected))

    await call.message.edit_reply_markup(
        reply_markup=channels_kb(data["channels"], selected)
    )

    await call.answer()

# ================= DONE =================
@dp.callback_query_handler(lambda c: c.data == "done", state=AdState.selecting)
async def done(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if not data.get("selected"):
        return await call.answer("❗ Tanlanmadi", show_alert=True)

    await call.message.edit_text("📩 Kontent yuboring (text/photo/video)")
    await AdState.content.set()

# ================= SEND =================
@dp.message_handler(state=AdState.content, content_types=types.ContentType.ANY)
async def send_ads(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected", [])

    text = msg.text or msg.caption or ""
    smart_text = smart_format(text) if text else None

    success = 0

    for cid in selected:
        try:
            if msg.content_type == "text":
                await bot.send_message(
                    chat_id=int(cid),
                    text=smart_text,
                    entities=msg.entities
                )
            else:
                await msg.send_copy(chat_id=int(cid))

            success += 1
        except Exception as e:
            print("ERROR:", e)

    await msg.answer(f"✅ {success} ta kanalga yuborildi 🚀")
    await state.finish()

# ================= WEB =================
async def handler(request):
    return web.Response(text="Bot running")

async def start_web():
    app = web.Application()
    app.router.add_get("/", handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()

# ================= STARTUP =================
async def on_startup(dp):
    asyncio.create_task(start_web())
    print("🚀 Bot ishga tushdi")

# ================= RUN =================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
