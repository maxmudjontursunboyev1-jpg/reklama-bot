import os
import asyncio
import logging
import gspread
from datetime import datetime
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
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

class BotStates(StatesGroup):
    add_channel = State()
    selecting = State()
    content = State()

# --- GOOGLE SHEETS ULANISH (ENiGMA VARIANTI) ---
def get_google_sheet():
    try:
        # To'liq ruxsatlar to'plami
        scope = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive"
        ]
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        sh = client.open_by_key(SPREADSHEET_ID)
        
        # Birinchi varaqni yoki Sheet2 ni topish
        try:
            return sh.worksheet("Sheet2")
        except:
            # Agar Sheet2 bo'lmasa, birinchi varaqni olamiz
            return sh.get_worksheet(0)
    except Exception as e:
        logger.error(f"⚠️ Sheets ulanishda kritik xato: {e}")
        return None

# --- HANDLERS ---

@dp.message_handler(commands=['start'], state="*")
async def cmd_start(message: types.Message, state: FSMContext):
    await state.finish()
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    kb.add("➕ Kanal qo'shish", "📢 Reklama yuborish", "📊 Statistika")
    
    welcome = (
        "👑 <b>Professional Ads Manager</b>\n\n"
        "Ushbu bot orqali kanallaringizga premium reklamalar yuborishingiz mumkin.\n"
        "Barcha ma'lumotlar Google Sheets bilan sinxronlangan."
    )
    await message.answer(welcome, reply_markup=kb)

# KANAL QO'SHISH MANTIQI
@dp.message_handler(text="➕ Kanal qo'shish", state="*")
async def add_start(message: types.Message):
    await message.answer(
        "📝 <b>Kanal qo'shish tartibi:</b>\n\n"
        "1. Botni kanalingizga admin qiling.\n"
        "2. Kanaldan istalgan postni menga <b>Forward</b> qiling.\n\n"
        "<i>Men kanal ID va nomini avtomatik aniqlayman.</i>"
    )
    await BotStates.add_channel.set()

@dp.message_handler(state=BotStates.add_channel, content_types=types.ContentTypes.ANY)
async def process_channel(message: types.Message, state: FSMContext):
    # Forward qilinganligini tekshirish
    if not message.forward_from_chat:
        return await message.answer("❌ Bu forward qilingan xabar emas. Iltimos, kanaldan xabar uzating.")
    
    chat = message.forward_from_chat
    if chat.type != 'channel':
        return await message.answer("❌ Bu kanal emas. Guruh yoki bot qo'shib bo'lmaydi.")

    wait_msg = await message.answer("⏳ Bazaga ulanilmoqda...")
    
    sheet = get_google_sheet()
    if sheet:
        try:
            # Bazada borligini tekshirish
            all_ids = sheet.col_values(2) # channel_id ustuni
            if str(chat.id) in all_ids:
                await wait_msg.edit_text("⚠️ Bu kanal allaqachon bazada mavjud!")
            else:
                # Yangi qator qo'shish
                sheet.append_row([
                    str(message.from_user.id), 
                    str(chat.id), 
                    chat.title, 
                    datetime.now().strftime("%d.%m.%Y %H:%M")
                ])
                await wait_msg.edit_text(f"✅ <b>{chat.title}</b> muvaffaqiyatli qo'shildi!")
        except Exception as e:
            await wait_msg.edit_text(f"❌ Xatolik yuz berdi: {e}")
    else:
        await wait_msg.edit_text("❌ Google Sheets bilan aloqa o'rnatib bo'lmadi. Credentials yoki IDni tekshiring.")
    
    await state.finish()

# REKLAMA TANLASH (MUKAMMAL TOGGLE)
@dp.message_handler(text="📢 Reklama yuborish", state="*")
async def ads_start(message: types.Message, state: FSMContext):
    sheet = get_google_sheet()
    if not sheet: return await message.answer("❌ Baza bilan aloqa yo'q.")
    
    records = sheet.get_all_records()
    kb = types.InlineKeyboardMarkup(row_width=1)
    
    count = 0
    for r in records:
        if message.from_user.id == ADMIN_ID or str(r.get('user_id')) == str(message.from_user.id):
            kb.add(types.InlineKeyboardButton(text=f"⚪ {r['title']}", callback_data=f"ch_{r['channel_id']}"))
            count += 1
    
    if count == 0:
        await message.answer("🤷‍♂️ Sizda hali qo'shilgan kanallar yo'q.")
    else:
        kb.add(types.InlineKeyboardButton("✅ Tanladim", callback_data="done"))
        await state.update_data(selected=[])
        await message.answer("📍 Reklama uchun kanallarni tanlang:", reply_markup=kb)
        await BotStates.selecting.set()

@dp.callback_query_handler(lambda c: c.data.startswith('ch_'), state=BotStates.selecting)
async def toggle(call: types.CallbackQuery, state: FSMContext):
    ch_id = call.data.split('_')[1]
    data = await state.get_data()
    selected = data.get('selected', [])
    
    if ch_id in selected: selected.remove(ch_id)
    else: selected.append(ch_id)
    
    await state.update_data(selected=selected)
    
    # Tugmalarni yangilash
    kb = types.InlineKeyboardMarkup(row_width=1)
    sheet = get_google_sheet()
    records = sheet.get_all_records()
    for r in records:
        if call.from_user.id == ADMIN_ID or str(r.get('user_id')) == str(call.from_user.id):
            mark = "🟢" if str(r['channel_id']) in selected else "⚪"
            kb.add(types.InlineKeyboardButton(text=f"{mark} {r['title']}", callback_data=f"ch_{r['channel_id']}"))
    kb.add(types.InlineKeyboardButton("✅ Tanladim", callback_data="done"))
    
    await call.message.edit_reply_markup(reply_markup=kb)

@dp.callback_query_handler(text="done", state=BotStates.selecting)
async def selection_done(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get('selected'):
        return await call.answer("⚠️ Kanal tanlang!", show_alert=True)
    await call.message.answer("🖼 Reklama xabarini yuboring (Premium emojilar va formatlash saqlanadi):")
    await BotStates.content.set()

@dp.message_handler(state=BotStates.content, content_types=types.ContentTypes.ANY)
async def final_broadcast(message: types.Message, state: FSMContext):
    data = await state.get_data()
    channels = data.get('selected')
    
    report = await message.answer("🚀 Reklama tarqatilmoqda...")
    success = 0
    
    for cid in channels:
        try:
            await message.send_copy(chat_id=cid)
            success += 1
            await asyncio.sleep(0.1)
        except: pass
        
    await state.finish()
    await report.edit_text(f"✅ Tayyor!\n🎯 {success} ta kanalga yuborildi.")

# --- WEB SERVER ---
async def handle(request): return web.Response(text="Bot is operational!")
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
