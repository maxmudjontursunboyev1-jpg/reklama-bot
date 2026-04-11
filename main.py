import logging
import aiohttp
from urllib.parse import quote

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

API_TOKEN = "7732017441:AAG9hIrPYuWiSRcNtJoo8uyXP2qJVSf4YpM"
API_URL = "https://script.google.com/macros/s/AKfycbxXesDKnT-BR8qHYNZm8X-WbdasojOr9-R2xN57nLlWvE3ARTy8poxs-e_Ss73svpiLXA/exec"
ADMIN_ID = 7339714216

logging.basicConfig(level=logging.INFO)

bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

# ================= STATES =================
class AddChat(StatesGroup):
    waiting = State()

class AdState(StatesGroup):
    choosing_type = State()
    selecting = State()
    content = State()
    buttons = State()
    button_text = State()
    button_url = State()

# ================= API =================
async def api_get(user_id):
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{API_URL}?action=get&user_id={user_id}") as r:
            return await r.json()

async def api_add(user_id, chat_id, title, type_):
    title = quote(title)
    async with aiohttp.ClientSession() as s:
        async with s.get(
            f"{API_URL}?action=add&user_id={user_id}&chat_id={chat_id}&title={title}&type={type_}"
        ) as r:
            return await r.json()

async def log_ads(user_id, count):
    async with aiohttp.ClientSession() as s:
        await s.get(f"{API_URL}?action=log&user_id={user_id}&count={count}")

async def get_stats():
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{API_URL}?action=stats") as r:
            return await r.json()

# ================= UI =================
def main_menu(user_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Qo‘shish", callback_data="add"))
    kb.add(InlineKeyboardButton("📢 Reklama", callback_data="ads"))
    kb.add(InlineKeyboardButton("📂 Meninglar", callback_data="my"))
    if user_id == ADMIN_ID:
        kb.add(InlineKeyboardButton("📊 Admin", callback_data="admin"))
    return kb

def back_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("🏠 Menu", callback_data="menu"))
    return kb

def type_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📢 Kanallar", callback_data="type_channel"))
    kb.add(InlineKeyboardButton("👥 Guruhlar", callback_data="type_group"))
    kb.add(InlineKeyboardButton("🌐 Hammasi", callback_data="type_all"))
    kb.add(InlineKeyboardButton("❌ Bekor", callback_data="menu"))
    return kb

def select_kb(chats, selected):
    kb = InlineKeyboardMarkup()
    for ch in chats:
        cid = str(ch["chat_id"])
        icon = "🟢" if cid in selected else "⚪"
        kb.add(InlineKeyboardButton(f"{icon} {ch['title']}", callback_data=f"toggle:{cid}"))
    kb.add(InlineKeyboardButton("✅ Tanladim", callback_data="done"))
    return kb

# ================= START =================
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    await msg.answer("👋 Xush kelibsiz", reply_markup=main_menu(msg.from_user.id))

@dp.callback_query_handler(lambda c: c.data == "menu", state="*")
async def menu(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.message.edit_text("🏠 Menu", reply_markup=main_menu(call.from_user.id))

# ================= ADD =================
@dp.callback_query_handler(lambda c: c.data == "add")
async def add(call: types.CallbackQuery):
    await call.message.edit_text("📩 Forward qiling")
    await AddChat.waiting.set()

@dp.message_handler(state=AddChat.waiting, content_types=types.ContentType.ANY)
async def save(msg: types.Message, state: FSMContext):
    if not msg.forward_from_chat:
        return await msg.answer("❌ Forward qiling")

    chat = msg.forward_from_chat
    type_ = "channel" if chat.type == "channel" else "group"

    data = await api_get(msg.from_user.id)
    for ch in data:
        if str(ch["chat_id"]) == str(chat.id):
            return await msg.answer("⚠️ Allaqachon bor")

    await api_add(msg.from_user.id, chat.id, chat.title, type_)

    await msg.answer(f"✅ Qo‘shildi: {chat.title}", reply_markup=main_menu(msg.from_user.id))
    await state.finish()

# ================= MY =================
@dp.callback_query_handler(lambda c: c.data == "my")
async def my(call: types.CallbackQuery):
    data = await api_get(call.from_user.id)

    if not data:
        return await call.message.edit_text("❌ Bo‘sh", reply_markup=back_kb())

    text = "📂 Ro‘yxat:\n\n"
    for ch in data:
        icon = "📢" if ch["type"] == "channel" else "👥"
        text += f"{icon} {ch['title']}\n"

    await call.message.edit_text(text, reply_markup=back_kb())

# ================= ADS =================
@dp.callback_query_handler(lambda c: c.data == "ads")
async def ads(call: types.CallbackQuery):
    await call.message.edit_text("Tanlang:", reply_markup=type_kb())
    await AdState.choosing_type.set()

@dp.callback_query_handler(lambda c: c.data.startswith("type_"), state=AdState.choosing_type)
async def choose(call: types.CallbackQuery, state: FSMContext):
    t = call.data.split("_")[1]
    data = await api_get(call.from_user.id)

    if t == "all":
        selected = [str(x["chat_id"]) for x in data]
        await state.update_data(selected=selected)
        await call.message.answer("📩 Kontent yuboring")
        return await AdState.content.set()

    filtered = [x for x in data if x["type"] == t]

    await state.update_data(chats=filtered, selected=[])

    await call.message.edit_text("Tanlang:", reply_markup=select_kb(filtered, []))
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
    await call.message.edit_reply_markup(reply_markup=select_kb(data["chats"], selected))

# ================= DONE =================
@dp.callback_query_handler(lambda c: c.data == "done", state=AdState.selecting)
async def done(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get("selected"):
        return await call.answer("Tanlanmadi", show_alert=True)

    await call.message.answer("📩 Kontent yuboring")
    await AdState.content.set()

# ================= CONTENT + PREVIEW =================
@dp.message_handler(state=AdState.content, content_types=types.ContentType.ANY)
async def content(msg: types.Message, state: FSMContext):
    await state.update_data(content=msg, buttons=[])

    await msg.answer("👁 Preview:")
    await msg.send_copy(msg.chat.id)

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Tugma", callback_data="add_btn"))
    kb.add(InlineKeyboardButton("🚀 Yuborish", callback_data="send"))

    await msg.answer("Davom etamizmi?", reply_markup=kb)
    await AdState.buttons.set()

# ================= BUTTON =================
@dp.callback_query_handler(lambda c: c.data == "add_btn", state=AdState.buttons)
async def add_btn(call: types.CallbackQuery):
    await call.message.answer("Matn:")
    await AdState.button_text.set()

@dp.message_handler(state=AdState.button_text)
async def btn_text(msg: types.Message, state: FSMContext):
    await state.update_data(temp=msg.text)
    await msg.answer("Link:")
    await AdState.button_url.set()

@dp.message_handler(state=AdState.button_url)
async def btn_url(msg: types.Message, state: FSMContext):
    data = await state.get_data()
    buttons = data.get("buttons", [])

    buttons.append({"text": data["temp"], "url": msg.text})
    await state.update_data(buttons=buttons)

    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Yana", callback_data="add_btn"))
    kb.add(InlineKeyboardButton("🚀 Yuborish", callback_data="send"))

    await msg.answer("Qo‘shildi", reply_markup=kb)
    await AdState.buttons.set()

# ================= SEND =================
@dp.callback_query_handler(lambda c: c.data == "send", state=AdState.buttons)
async def send(call: types.CallbackQuery, state: FSMContext):
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
    failed = []

    for cid in selected:
        try:
            await content.send_copy(chat_id=cid, reply_markup=kb)
            success += 1
        except:
            failed.append(cid)

    await log_ads(call.from_user.id, success)

    text = f"✅ {success} ta yuborildi"
    if failed:
        text += f"\n❌ {len(failed)} ta xato"

    await call.message.answer(text, reply_markup=main_menu(call.from_user.id))
    await state.finish()

# ================= ADMIN =================
@dp.callback_query_handler(lambda c: c.data == "admin")
async def admin(call: types.CallbackQuery):
    if call.from_user.id != ADMIN_ID:
        return

    stats = await get_stats()

    text = f"""
📊 Statistika

👤 Users: {stats['users']}
📢 Ads: {stats['total_ads']}
"""

    await call.message.edit_text(text, reply_markup=back_kb())

# ================= RUN =================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
