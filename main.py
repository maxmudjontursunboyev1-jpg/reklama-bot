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
from aiohttp import web

# --- KONFIGURATSIYA (ENV) ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 7339714216))
SPREADSHEET_ID = "175HMek0SGGy9u6xKzpdVlbJmppRksKonxSjZNVUA2lQ"

# Loglarni sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Bot va Dispatcher (Xotira bilan)
bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- GOOGLE SHEETS TIZIMI ---
def get_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SPREADSHEET_ID).sheet1
    except Exception as e:
        logger.error(f"Google Sheets ulanish xatosi: {e}")
        return None

def register_user(user: types.User, chat_type):
    sheet = get_sheets()
    if sheet:
        try:
            user_id = str(user.id)
            ids = sheet.col_values(1)
            if user_id not in ids:
                now = datetime.now().strftime("%d.%m.%Y %H:%M")
                sheet.append_row([user_id, user.full_name, f"@{user.username}", chat_type, now])
                logger.info(f"Yangi foydalanuvchi bazaga qo'shildi: {user.full_name}")
        except Exception as e:
            logger.error(f"Bazaga yozishda xato: {e}")

# --- ADMIN KLAVIATURASI ---
def admin_keyboard():
    kb = types.InlineKeyboardMarkup(row_width=2)
    kb.add(
        types.InlineKeyboardButton("📊 Statistika", callback_data="stats"),
        types.InlineKeyboardButton("📢 Reklama (Yangi)", callback_data="send_ad"),
        types.InlineKeyboardButton("🔄 Forward Reklama", callback_data="forward_ad"),
        types.InlineKeyboardButton("📄 Bazani ko'rish", url=f"https://docs.google.com/spreadsheets/d/{SPREADSHEET_ID}")
    )
    return kb

# --- HANDLERLAR ---

# Admin Panel (Faqat Admin uchun)
@dp.message_handler(commands=['admin'], user_id=ADMIN_ID)
async def admin_panel(message: types.Message):
    await message.answer("🛠 <b>Admin Panelga xush kelibsiz!</b>\nQuyidagi amallardan birini tanlang:", reply_markup=admin_keyboard())

# Start Buyrug'i
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    register_user(message.from_user, message.chat.type)
    
    welcome_text = (
        f"<b>Assalomu alaykum, {message.from_user.first_name}!</b> 👋\n\n"
        "Men professional botman. Xizmatlarimizdan foydalanish uchun "
        "quyidagi menyulardan foydalanishingiz mumkin."
    )
    
    # Oddiy foydalanuvchi uchun tugmalar (ixtiyoriy qo'shish mumkin)
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add("ℹ️ Ma'lumot", "📞 Aloqa")
    
    await message.answer(welcome_text, reply_markup=kb)
    if message.from_user.id == ADMIN_ID:
        await message.answer("💡 Siz adminsiz, /admin buyrug'ini yozishingiz mumkin.")

# Statistika Callback
@dp.callback_query_handler(text="stats", user_id=ADMIN_ID)
async def show_stats(call: types.CallbackQuery):
    sheet = get_sheets()
    if sheet:
        count = len(sheet.col_values(1)) - 1
        await call.message.edit_text(f"📊 <b>Bot statistikasi:</b>\n\nJami foydalanuvchilar: <b>{count} ta</b>", reply_markup=admin_keyboard())
    else:
        await call.answer("Baza bilan bog'lanib bo'lmadi.")

# Reklama yuborish bosqichi
@dp.callback_query_handler(text=["send_ad", "forward_ad"], user_id=ADMIN_ID)
async def ad_type_chosen(call: types.CallbackQuery, state: FSMContext):
    await state.update_data(ad_type=call.data)
    await call.message.answer("📝 Reklama xabarini yuboring (matn, rasm yoki video):")
    await state.set_state("waiting_for_ad_content")

@dp.message_handler(state="waiting_for_ad_content", content_types=types.ContentTypes.ANY, user_id=ADMIN_ID)
async def broadcast_ad(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ad_type = data.get("ad_type")
    await state.finish()

    sheet = get_sheets()
    user_ids = sheet.col_values(1)[1:] # Sarlavhadan tashqari hamma IDlar
    
    success, fail = 0, 0
    msg = await message.answer("🚀 Tarqatish boshlandi...")

    for uid in user_ids:
        try:
            if ad_type == "forward_ad":
                await bot.forward_message(uid, message.chat.id, message.message_id)
            else:
                await bot.copy_message(uid, message.chat.id, message.message_id)
            success += 1
            await asyncio.sleep(0.05) # Telegram bloklamasligi uchun
        except Exception:
            fail += 1
            
    await msg.edit_text(f"✅ <b>Natija:</b>\n\nYuborildi: {success} ta\nMuvaffaqiyatsiz: {fail} ta")

# --- WEB SERVER (RENDER UCHUN) ---
async def handle(request):
    return web.Response(text="Bot is operational. 🛡️")

async def start_web_server():
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', int(os.environ.get("PORT", 8080)))
    await site.start()

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.create_task(start_web_server())
    executor.start_polling(dp, skip_updates=True)
