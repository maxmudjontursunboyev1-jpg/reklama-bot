import os
import asyncio
import logging
from datetime import datetime

import gspread
from oauth2client.service_account import ServiceAccountCredentials
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiohttp import web

# --- CONFIG ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 7339714216))
SPREADSHEET_ID = "175HMek0SGGy9u6xKzpdVlbJmppRksKonxSjZNVUA2lQ"

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- GOOGLE SHEETS CORE ---
def get_db():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        
        # Sheet2 ni nomi bo'yicha qidiramiz (Indeksga bog'lanib qolmaslik uchun)
        try:
            worksheet = spreadsheet.worksheet("Sheet2")
        except gspread.WorksheetNotFound:
            # Agar Sheet2 bo'lmasa, uni yaratamiz
            worksheet = spreadsheet.add_worksheet(title="Sheet2", rows="100", cols="20")
            worksheet.append_row(["user_id", "channel_id", "title", "date"])
        
        return worksheet
    except Exception as e:
        logger.error(f"Sheets ulanish xatosi: {e}")
        return None

# --- DATABASE LOGIC ---
def fetch_channels(user_id):
    sheet = get_db()
    if not sheet: return {}
    
    try:
        records = sheet.get_all_records()
        channels = {}
        for r in records:
            # Admin barchasini ko'radi, foydalanuvchi faqat o'zinikini
            if user_id == ADMIN_ID or str(r.get('user_id')) == str(user_id):
                cid = r.get('channel_id')
                title = r.get('title')
                if cid and title:
                    channels[int(cid)] = title
        return channels
    except Exception as e:
        logger.error(f"O'qishda xato: {e}")
        return {}

# --- STATES ---
class BotStates(StatesGroup):
    add_channel = State()
    selecting = State()
    content = State()

# --- KEYBOARDS ---
def main_menu(user_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("➕ Kanal qo'shish", "📢 Reklama yuborish")
    if user_id == ADMIN_ID:
        kb.row("📊 Statistika")
    return kb

def build_channel_kb(user_id, selected=[]):
    channels = fetch_channels(user_id)
    kb = types.InlineKeyboardMarkup(row_width=1)
    if channels:
        for cid, title in channels.items():
            mark = "🟢" if cid in selected else "⚪"
            kb.add(types.InlineKeyboardButton(text=f"{mark} {title}", callback_data=f"toggle_{cid}"))
        kb.add(types.InlineKeyboardButton("✅ Tanlab bo'ldim", callback_data="done"))
    else:
        kb.add(types.InlineKeyboardButton("🤷‍♂️ Hali kanallar yo'q", callback_data="none"))
    return kb

# --- HANDLERS ---

@dp.message_handler(commands=['start'], state="*")
async def start(message: types.Message, state: FSMContext):
    await state.finish()
    await message.answer(f"👋 Salom {message.from_user.first_name}! Tizim tayyor.", 
                         reply_markup=main_menu(message.from_user.id))

# KANAL QO'SHISH
@dp.message_handler(text="➕ Kanal qo'shish", state="*")
async def ask_channel(message: types.Message):
    await message.answer("📢 Botni kanalga <b>Admin</b> qiling va kanaldan xabarni menga <b>Forward</b> qiling.")
    await BotStates.add_channel.set()

@dp.message_handler(state=BotStates.add_channel, is_forwarded=True, content_types=types.ContentTypes.ANY)
async def save_channel(message: types.Message, state: FSMContext):
    if message.forward_from_chat:
        chat = message.forward_from_chat
        sheet = get_db()
        if sheet:
            sheet.append_row([str(message.from_user.id), str(chat.id), chat.title, datetime.now().strftime("%d.%m.%Y")])
            await message.answer(f"✅ <b>{chat.title}</b> bazaga muvaffaqiyatli qo'shildi!")
        await state.finish()
    else:
        await message.answer("❌ Bu kanaldan uzatilgan xabar emas.")

# REKLAMA JARAYONI
@dp.message_handler(text="📢 Reklama yuborish", state="*")
async def start_ads(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    kb = build_channel_kb(uid)
    if "🤷‍♂️" in kb.inline_keyboard[0][0].text:
        await message.answer("🤷‍♂️ Sizda hali qo'shilgan kanallar yo'q.")
    else:
        await state.update_data(selected=[])
        await message.answer("📍 Reklama uchun kanallarni tanlang:", reply_markup=kb)
        await BotStates.selecting.set()

@dp.callback_query_handler(lambda c: c.data.startswith('toggle_'), state=BotStates.selecting)
async def toggle(call: types.CallbackQuery, state: FSMContext):
    cid = int(call.data.split('_')[1])
    data = await state.get_data()
    selected = data.get('selected', [])
    if cid in selected: selected.remove(cid)
    else: selected.append(cid)
    await state.update_data(selected=selected)
    await call.message.edit_reply_markup(reply_markup=build_channel_kb(call.from_user.id, selected))

@dp.callback_query_handler(text="done", state=BotStates.selecting)
async def done_selection(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get('selected'):
        return await call.answer("⚠️ Kamida bitta kanal tanlang!", show_alert=True)
    await call.message.answer("🖼 Reklama xabarini yuboring (Media, Matn, Premium Emoji):")
    await BotStates.content.set()

@dp.message_handler(state=BotStates.content, content_types=types.ContentTypes.ANY)
async def broadcast(message: types.Message, state: FSMContext):
    data = await state.get_data()
    channels = data.get('selected')
    wait_msg = await message.answer("🚀 Reklama tarqatilmoqda, kuting...")
    
    success = 0
    for cid in channels:
        try:
            # send_copy barcha premium emojilarni va formatlashni saqlaydi
            await message.send_copy(chat_id=cid)
            success += 1
            await asyncio.sleep(0.1)
        except Exception as e:
            logger.error(f"Yuborishda xato {cid}: {e}")
            
    await state.finish()
    await wait_msg.edit_text(f"✅ Jarayon yakunlandi!\n🎯 Yuborildi: {success} ta kanalga.")

# --- SERVER ---
async def handle(request): return web.Response(text="Bot is Live")
async def start_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(start_server())
    executor.start_polling(dp, skip_updates=True)
