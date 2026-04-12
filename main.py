import logging
import aiohttp
import asyncio
import datetime
from urllib.parse import quote

from aiogram import Bot, Dispatcher, types
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor

API_TOKEN = "7732017441:AAHXi-rcV2be8qXAE-so43mh2n4rtzVZbc4"
API_URL = "https://script.google.com/macros/s/AKfycbw7uZSzJxFVXTsbvf6-s35qujZcKtyQGqSTNeZTI0_9Bqbe2dYHebfIzbmWolOc0oC47Q/exec"
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
    schedule_time = State()

# ================= API =================
async def safe_json(r):
    try:
        return await r.json()
    except:
        print("RAW:", await r.text())
        return []

async def api_get(user_id):
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{API_URL}?action=get&user_id={user_id}") as r:
            return await safe_json(r)

async def api_add(user_id, chat_id, title, type_):
    title = quote(title)
    async with aiohttp.ClientSession() as s:
        async with s.get(f"{API_URL}?action=add&user_id={user_id}&chat_id={chat_id}&title={title}&type={type_}") as r:
            return await safe_json(r)

async def log_ads(user_id, count):
    async with aiohttp.ClientSession() as s:
        await s.get(f"{API_URL}?action=log&user_id={user_id}&count={count}")

# ================= SEND SYSTEM =================
async def send_post(bot, msg, chat_id, kb=None):
    try:
        if msg.content_type == "text":
            await bot.send_message(chat_id, msg.text, entities=msg.entities, reply_markup=kb)

        elif msg.content_type == "photo":
            await bot.send_photo(chat_id, msg.photo[-1].file_id,
                                 caption=msg.caption,
                                 caption_entities=msg.caption_entities,
                                 reply_markup=kb)

        elif msg.content_type == "video":
            await bot.send_video(chat_id, msg.video.file_id,
                                 caption=msg.caption,
                                 caption_entities=msg.caption_entities,
                                 reply_markup=kb)

        elif msg.content_type == "animation":
            await bot.send_animation(chat_id, msg.animation.file_id,
                                     caption=msg.caption,
                                     caption_entities=msg.caption_entities,
                                     reply_markup=kb)

        elif msg.content_type == "sticker":
            await bot.send_sticker(chat_id, msg.sticker.file_id)

        else:
            await msg.send_copy(chat_id, reply_markup=kb)

        return True

    except Exception as e:
        print("SEND ERROR:", e)
        return False

# ================= UI =================
def main_menu(user_id):
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("➕ Qo‘shish", callback_data="add"))
    kb.add(InlineKeyboardButton("📢 Reklama", callback_data="ads"))
    kb.add(InlineKeyboardButton("📂 Meninglar", callback_data="my"))
    return kb

def type_kb():
    kb = InlineKeyboardMarkup()
    kb.add(InlineKeyboardButton("📢 Kanallar", callback_data="type_channel"))
    kb.add(InlineKeyboardButton("👥 Guruhlar", callback_data="type_group"))
    kb.add(InlineKeyboardButton("🌐 Hammasi", callback_data="type_all"))
    return kb

def select_kb(chats, selected):
    kb = InlineKeyboardMarkup()
    for ch in chats:
        cid = str(ch["chat_id"])
        icon = "🟢" if cid in selected else "⚪"
        kb.add(InlineKeyboardButton(f"{icon} {ch['title']}", callback_data=f"toggle:{cid}"))
    kb.add(InlineKeyboardButton("✅ Tanladim", callback_data="done"))
    return kb

def preview_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("✏️ Edit", callback_data="edit"),
        InlineKeyboardButton("➕ Tugma", callback_data="add_btn"),
    )
    kb.add(
        InlineKeyboardButton("⏰ Schedule", callback_data="schedule"),
        InlineKeyboardButton("🚀 Yuborish", callback_data="send")
    )
    kb.add(InlineKeyboardButton("❌ Bekor", callback_data="cancel"))
    return kb

def build_buttons(buttons):
    kb = InlineKeyboardMarkup(row_width=2)
    row = []
    for i, b in enumerate(buttons, 1):
        row.append(InlineKeyboardButton(b["text"], url=b["url"]))
        if i % 2 == 0:
            kb.row(*row)
            row = []
    if row:
        kb.row(*row)
    return kb

# ================= START =================
@dp.message_handler(commands=['start'])
async def start(msg: types.Message):
    await msg.answer("👋 Xush kelibsiz", reply_markup=main_menu(msg.from_user.id))

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

@dp.callback_query_handler(lambda c: c.data == "done", state=AdState.selecting)
async def done(call: types.CallbackQuery, state: FSMContext):
    await call.message.answer("📩 Kontent yuboring")
    await AdState.content.set()

# ================= CONTENT =================
@dp.message_handler(state=AdState.content, content_types=types.ContentType.ANY)
async def content(msg: types.Message, state: FSMContext):
    await state.update_data(content=msg, buttons=[])

    await msg.answer("👁 Preview:")
    await send_post(bot, msg, msg.chat.id)

    await msg.answer("Davom etamizmi?", reply_markup=preview_kb())
    await AdState.buttons.set()

# ================= BUTTON ADD =================
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

    await msg.answer("Qo‘shildi", reply_markup=preview_kb())
    await AdState.buttons.set()

# ================= SEND =================
@dp.callback_query_handler(lambda c: c.data == "send", state=AdState.buttons)
async def send(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()

    kb = build_buttons(data["buttons"]) if data.get("buttons") else None

    success = 0
    for cid in data["selected"]:
        ok = await send_post(bot, data["content"], int(cid), kb)
        if ok:
            success += 1

    await log_ads(call.from_user.id, success)

    await call.message.answer(f"✅ {success} ta yuborildi",
                              reply_markup=main_menu(call.from_user.id))
    await state.finish()

# ================= CANCEL =================
@dp.callback_query_handler(lambda c: c.data == "cancel", state="*")
async def cancel(call: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await call.message.edit_text("❌ Bekor qilindi", reply_markup=main_menu(call.from_user.id))

# ================= RUN =================
if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
