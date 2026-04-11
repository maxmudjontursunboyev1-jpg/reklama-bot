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
API_TOKEN = "7732017441:AAEjb82urs4zeNFgr8Mw94OuKtQL_6lcvL4"
ADMIN_ID = 7339714216
API_URL = "https://script.google.com/macros/s/AKfycbzffXKXTzbGARB68yt9h65hVvI9f9qRmz89ZR-ilmhOCSB2F1AeRWvGpfPuhQ8apE7niA/exec"

bot = Bot(token=API_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())

logging.basicConfig(level=logging.INFO)

# ================= STATES =================
class AddChannel(StatesGroup):
    waiting_forward = State()

class AdState(StatesGroup):
    selecting = State()
    content = State()
    buttons = State()
    button_text = State()
    button_url = State()

# ================= API =================
async def api_get(user_id):
    async with aiohttp.ClientSession() as session:
        async with session.get(f"{API_URL}?action=get&user_id={user_id}") as resp:
            return await resp.json()

async def api_add(user_id, channel_id, title):
    async with aiohttp.ClientSession() as session:
        await session.get(f"{API_URL}?action=add&user_id={user_id}&channel_id={channel_id}&title={title}")

# ================= UI =================
def main_menu():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Kanal qo'shish", callback_data="add"))
    kb.add(InlineKeyboardButton("📢 Reklama yaratish", callback_data="ads"))
    return kb

def channels_kb(channels, selected):
    kb = InlineKeyboardMarkup()
    for ch in channels:
        cid = str(ch["channel_id"])
        icon = "🟢" if cid in selected else "⚪"
        kb.add(InlineKeyboardButton(f"{icon} {ch['title']}", callback_data=f"toggle:{cid}"))
    kb.add(InlineKeyboardButton("✅ Tanladim", callback_data="done"))
    kb.add(InlineKeyboardButton("❌ Bekor qilish", callback_data="cancel"))
    return kb

# ================= START =================
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    await msg.answer("👋 Xush kelibsiz!", reply_markup=main_menu())

# ================= CANCEL =================
@dp.callback_query_handler(lambda c: c.data == "cancel", state="*")
async def cancel(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.message.edit_text("🏠 Menu", reply_markup=main_menu())

# ================= ADD CHANNEL =================
@dp.callback_query_handler(lambda c: c.data == "add", state="*")
async def add_start(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.message.edit_text("📩 Kanal postini forward qiling")
    await AddChannel.waiting_forward.set()

@dp.message_handler(state=AddChannel.waiting_forward, content_types=types.ContentType.ANY)
async def save_channel(msg: types.Message, state: FSMContext):
    if not msg.forward_from_chat or msg.forward_from_chat.type != "channel":
        return await msg.answer("❌ Faqat kanal postini forward qiling")

    chat = msg.forward_from_chat
    await api_add(msg.from_user.id, chat.id, chat.title)

    await msg.answer(f"✅ Qo'shildi: {chat.title}")
    await state.finish()

# ================= ADS =================
@dp.callback_query_handler(lambda c: c.data == "ads", state="*")
async def ads(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    channels = await api_get(call.from_user.id)

    if not channels:
        return await call.message.answer("❌ Kanal yo‘q")

    await state.update_data(channels=channels, selected=[])
    await call.message.edit_text("📌 Tanlang:", reply_markup=channels_kb(channels, []))
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
    await call.message.edit_reply_markup(reply_markup=channels_kb(data["channels"], selected))

# ================= DONE =================
@dp.callback_query_handler(lambda c: c.data == "done", state=AdState.selecting)
async def done(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    if not data.get("selected"):
        return await call.answer("Tanlanmadi", show_alert=True)

    await call.message.answer("📩 Reklama yuboring (text/photo/video/sticker)")
    await AdState.content.set()

# ================= CONTENT =================
@dp.message_handler(state=AdState.content, content_types=types.ContentType.ANY)
async def content(msg: types.Message, state: FSMContext):
    await state.update_data(content=msg, buttons=[])

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Tugma qo‘shish", callback_data="add_btn"))
    kb.add(InlineKeyboardButton("🚀 Yuborish", callback_data="send_now"))

    await msg.answer("🔘 Tugma qo‘shasizmi?", reply_markup=kb)
    await AdState.buttons.set()

# ================= ADD BUTTON =================
@dp.callback_query_handler(lambda c: c.data == "add_btn", state=AdState.buttons)
async def add_btn(call: types.CallbackQuery):
    await call.message.answer("✏️ Tugma matni:")
    await AdState.button_text.set()

@dp.message_handler(state=AdState.button_text)
async def btn_text(msg: types.Message, state: FSMContext):
    await state.update_data(temp_text=msg.text)
    await msg.answer("🔗 Link:")
    await AdState.button_url.set()

@dp.message_handler(state=AdState.button_url)
async def btn_url(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    buttons = data.get("buttons", [])

    buttons.append({
        "text": data["temp_text"],
        "url": msg.text
    })

    await state.update_data(buttons=buttons)

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Yana qo‘shish", callback_data="add_btn"))
    kb.add(InlineKeyboardButton("🚀 Yuborish", callback_data="send_now"))

    await msg.answer("✅ Tugma qo‘shildi", reply_markup=kb)
    await AdState.buttons.set()

# ================= SEND =================
@dp.callback_query_handler(lambda c: c.data == "send_now", state=AdState.buttons)
async def send_now(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    selected = data["selected"]
    content = data["content"]
    buttons = data.get("buttons", [])

    kb = None
    if buttons:
        kb = InlineKeyboardMarkup()
        for b in buttons:
            kb.add(InlineKeyboardButton(b["text"], url=b["url"]))

    success = 0

    for cid in selected:
        try:
            if content.content_type == "text":
                await bot.send_message(cid, content.text, reply_markup=kb)

            elif content.content_type == "sticker":
                await bot.send_sticker(cid, content.sticker.file_id)

            else:
                await content.send_copy(cid, reply_markup=kb)

            success += 1
        except Exception as e:
            print(e)

    await call.message.answer(f"✅ {success} ta kanalga yuborildi 🚀")
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

async def on_startup(dp):
    asyncio.create_task(start_web())

# ================= RUN =================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=False, on_startup=on_startup)
