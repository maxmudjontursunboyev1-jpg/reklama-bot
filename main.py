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

# --- KONFIGURATSIYA ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 7339714216))
SPREADSHEET_ID = "175HMek0SGGy9u6xKzpdVlbJmppRksKonxSjZNVUA2lQ"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- GOOGLE SHEETS BAZA BILAN ISHLASH ---
def get_worksheet(index=0):
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        spreadsheet = client.open_by_key(SPREADSHEET_ID)
        return spreadsheet.get_worksheet(index)
    except Exception as e:
        logging.error(f"Sheets xatosi: {e}")
        return None

# Kanallarni bazadan o'qish
def get_user_channels_from_db(user_id):
    sheet = get_worksheet(1) # Sheet2 - Kanallar uchun
    if not sheet: return {}
    all_records = sheet.get_all_records()
    return {int(r['channel_id']): r['title'] for r in all_records if int(r['user_id']) == user_id}

# Kanalni bazaga saqlash
def save_channel_to_db(user_id, channel_id, title):
    sheet = get_worksheet(1)
    if sheet:
        sheet.append_row([str(user_id), str(channel_id), title, datetime.now().strftime("%Y-%m-%d %H:%M")])

# --- STATES ---
class AdStates(StatesGroup):
    waiting_for_channel = State()
    selecting_channels = State()
    waiting_for_content = State()

# --- KEYBOARDS ---
def main_menu():
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("➕ Kanal qo'shish", "📢 Reklama yuborish")
    kb.row("📊 Statistika", "⚙️ Sozlamalar")
    return kb

def get_channel_keyboard(user_id, selected_channels=[]):
    channels = get_user_channels_from_db(user_id)
    kb = types.InlineKeyboardMarkup(row_width=1)
    if channels:
        for cid, title in channels.items():
            mark = "🟢" if cid in selected_channels else "⚪"
            kb.add(types.InlineKeyboardButton(text=f"{mark} {title}", callback_data=f"toggle_{cid}"))
        kb.add(types.InlineKeyboardButton("✅ Tanladim", callback_data="channels_done"))
    else:
        kb.add(types.InlineKeyboardButton("🤷‍♂️ Kanallar topilmadi", callback_data="none"))
    return kb

# --- HANDLERS ---

@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    # Foydalanuvchini Sheet1 ga yozish (Ixtiyoriy)
    await message.answer(f"👋 Salom {message.from_user.first_name}! Professional Reklama Botiga xush kelibsiz.", 
                         reply_markup=main_menu())

# KANAL QO'SHISH (FORWARD ORQALI)
@dp.message_handler(text="➕ Kanal qo'shish", state="*")
async def start_add_ch(message: types.Message):
    await message.answer("📢 Botni kanalingizga <b>Admin</b> qiling va kanaldan istalgan xabarni menga <b>Forward</b> qiling.")
    await AdStates.waiting_for_channel.set()

@dp.message_handler(state=AdStates.waiting_for_channel, is_forwarded=True, content_types=types.ContentTypes.ANY)
async def process_ch(message: types.Message, state: FSMContext):
    if message.forward_from_chat:
        chat = message.forward_from_chat
        uid = message.from_user.id
        
        # Bazada borligini tekshirish
        existing = get_user_channels_from_db(uid)
        if chat.id in existing:
            await message.answer("⚠️ Bu kanal allaqachon ro'yxatda bor.")
        else:
            save_channel_to_db(uid, chat.id, chat.title)
            await message.answer(f"✅ <b>{chat.title}</b> bazaga saqlandi!", reply_markup=main_menu())
        await state.finish()
    else:
        await message.answer("❌ Bu kanaldan uzatilgan xabar emas.")

# REKLAMA: KANAL TANLASH (DINAMIK TUGMALAR)
@dp.message_handler(text="📢 Reklama yuborish", state="*")
async def start_ads(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    channels = get_user_channels_from_db(uid)
    if not channels:
        return await message.answer("🤷‍♂️ Avval kanal qo'shishingiz kerak.")
    
    await state.update_data(selected_channels=[])
    await message.answer("📍 Reklama yubormoqchi bo'lgan kanallaringizni tanlang:", 
                         reply_markup=get_channel_keyboard(uid))
    await AdStates.selecting_channels.set()

@dp.callback_query_handler(lambda c: c.data.startswith('toggle_'), state=AdStates.selecting_channels)
async def toggle_ch(call: types.CallbackQuery, state: FSMContext):
    cid = int(call.data.split('_')[1])
    data = await state.get_data()
    selected = data.get('selected_channels', [])
    
    if cid in selected: selected.remove(cid)
    else: selected.append(cid)
    
    await state.update_data(selected_channels=selected)
    await call.message.edit_reply_markup(reply_markup=get_channel_keyboard(call.from_user.id, selected))
    await call.answer()

@dp.callback_query_handler(text="channels_done", state=AdStates.selecting_channels)
async def channels_done(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get('selected_channels'):
        return await call.answer("⚠️ Hech bo'lmasa bitta kanal tanlang!", show_alert=True)
    
    await call.message.answer("🖼 Reklama kontentini yuboring (Rasm, Video, Matn, Premium Emojilar):")
    await AdStates.waiting_for_content.set()

# REKLAMANI YUBORISH (PREMIUM EMOJI VA ENTITIES SAQLANADI)
@dp.message_handler(state=AdStates.waiting_for_content, content_types=types.ContentTypes.ANY)
async def send_bulk(message: types.Message, state: FSMContext):
    data = await state.get_data()
    channels = data.get('selected_channels')
    
    msg = await message.answer("🚀 Reklama tarqatilmoqda...")
    success, fail = 0, 0
    
    for cid in channels:
        try:
            # send_copy barcha entities va premium emojilarni saqlab qoladi
            await message.send_copy(chat_id=cid)
            success += 1
            await asyncio.sleep(0.1)
        except Exception:
            fail += 1
            
    await state.finish()
    await msg.edit_text(f"✅ <b>Yuborish tugadi!</b>\n\nMuvaffaqiyatli: {success}\nXato: {fail}", 
                        reply_markup=main_menu())

# --- WEB SERVER (RENDER) ---
async def handle(request): return web.Response(text="Bot Active 🔊")
async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    await web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080))).start()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(start_web_server())
    executor.start_polling(dp, skip_updates=True)
