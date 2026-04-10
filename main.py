import logging
import requests
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.dispatcher import FSMContext
from aiogram.types import ContentType

BOT_TOKEN = "7732017441:AAEBr-MUe_1MpdE3Ahpv5CAXwDxEYRMvYyA"
ADMIN_ID = 7339714216  # o'z ID'ingiz bilan almashtiring
SCRIPT_URL = "https://script.google.com/macros/s/AKfycbzffXKXTzbGARB68yt9h65hVvI9f9qRmz89ZR-ilmhOCSB2F1AeRWvGpfPuhQ8apE7niA/exec"

# --- logging
logging.basicConfig(level=logging.INFO)

# --- aiogram
bot = Bot(token=BOT_TOKEN, parse_mode="HTML")
dp = Dispatcher(bot, storage=MemoryStorage())


# --- FSM state
class AddChannel(StatesGroup):
    waiting_for_forward = State()


# --- asosiy menyu
def main_menu(user_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("➕ Kanal qo'shish", "📢 Reklama yuborish")
    if user_id == ADMIN_ID:
        kb.add("📊 Statistika")
    return kb


# --- Google Apps Script bilan ishlovchi bazaviy funksiyalar
def add_channel_to_sheets(user_id, channel_id, title):
    data = {
        "action": "add_channel",
        "user_id": str(user_id),
        "channel_id": str(channel_id),
        "title": title
    }
    r = requests.post(SCRIPT_URL, json=data, timeout=10)
    return r.text


def get_user_channels_from_sheets(user_id):
    data = {"action": "get_channels", "user_id": str(user_id)}
    r = requests.post(SCRIPT_URL, json=data, timeout=10)
    try:
        return r.json()
    except Exception:
        return []


def get_all_channels_from_sheets():
    data = {"action": "get_all"}
    r = requests.post(SCRIPT_URL, json=data, timeout=10)
    try:
        return r.json()
    except Exception:
        return []


# --- handlerlar
@dp.message_handler(commands=["start"])
async def cmd_start(m: types.Message):
    await m.answer(f"👋 Salom, <b>{m.from_user.first_name}</b>!\n\n"
                   "Men sizga kanallaringizga reklama yuborishda yordam beraman.",
                   reply_markup=main_menu(m.from_user.id))


@dp.message_handler(lambda m: m.text == "➕ Kanal qo'shish")
async def add_channel_btn(m: types.Message):
    await AddChannel.waiting_for_forward.set()
    await m.answer("📣 Kanalni qo‘shish uchun:\n\n"
                   "1️⃣ Botni kanalga admin qilib qo‘shing.\n"
                   "2️⃣ Kanaldan xabarni forward qiling.")


@dp.message_handler(content_types=ContentType.ANY, state=AddChannel.waiting_for_forward)
async def handle_forward(m: types.Message, state: FSMContext):
    if not m.forward_from_chat or m.forward_from_chat.type != "channel":
        await m.answer("❌ Iltimos, kanal xabarini forward qiling.")
        return
    ch = m.forward_from_chat
    try:
        me = await bot.get_chat_member(ch.id, bot.id)
        if me.status not in ["administrator", "creator"]:
            await m.answer(f"⚠️ Bot <b>{ch.title}</b> kanalida admin emas.")
            return
    except Exception:
        await m.answer("⚠️ Bot kanalga admin sifatida qo‘shilmagan.")
        return

    result = add_channel_to_sheets(m.from_user.id, ch.id, ch.title)
    await m.answer(f"{result}", reply_markup=main_menu(m.from_user.id))
    await state.finish()


@dp.message_handler(lambda m: m.text == "📢 Reklama yuborish")
async def send_ad(m: types.Message):
    channels = (get_all_channels_from_sheets() if m.from_user.id == ADMIN_ID
                else get_user_channels_from_sheets(m.from_user.id))
    if not channels:
        await m.answer("❌ Sizda saqlangan kanallar yo‘q.")
        return

    text = "📋 Tanlangan kanallar:\n"
    for ch in channels:
        if len(ch) >= 3:  # [user_id, channel_id, title, date]
            text += f"• {ch[2]} (ID: {ch[1]})\n"
    await m.answer(text)


@dp.message_handler(lambda m: m.text == "📊 Statistika")
async def stats(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        await m.answer("⛔ Faqat admin uchun.")
        return
    all_data = get_all_channels_from_sheets()
    users = {r[0] for r in all_data[1:]} if len(all_data) > 1 else set()
    msg = (f"📊 Statistika\n\n"
           f"👥 Foydalanuvchilar: {len(users)}\n"
           f"📢 Kanallar: {len(all_data) - 1}")
    await m.answer(msg)


if __name__ == "__main__":
    executor.start_polling(dp, skip_updates=True)
