import os
import asyncio
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from aiogram import Bot, Dispatcher, types
from aiohttp import web

# --- KONFIGURATSIYA ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 7339714216))
SPREADSHEET_ID = "175HMek0SGGy9u6xKzpdVlbJmppRksKonxSjZNVUA2lQ"

# Loglarni Render panelida ko'rish uchun sozlash
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot)

# --- GOOGLE SHEETS API ---
def get_sheets():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        # credentials.json fayli asosiy papkada ekanligiga ishonch hosil qiling
        creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
        client = gspread.authorize(creds)
        return client.open_by_key(SPREADSHEET_ID).sheet1
    except Exception as e:
        logger.error(f"Jadvalga ulanishda xato: {e}")
        return None

def log_to_sheet(chat_id, title, chat_type, user_id):
    sheet = get_sheets()
    if sheet:
        try:
            ids = sheet.col_values(1)
            if str(chat_id) not in ids:
                sheet.append_row([str(chat_id), str(title), str(chat_type), str(user_id)])
                logger.info(f"Yangi foydalanuvchi qo'shildi: {title}")
        except Exception as e:
            logger.error(f"Ma'lumot yozishda xato: {e}")

# --- HANDLERLAR ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    logger.info(f"Start buyrug'i keldi: {message.from_user.id}")
    
    # Ma'lumotni jadvalga yozishni sinab ko'ramiz
    log_to_sheet(message.chat.id, message.chat.title or message.from_user.full_name, message.chat.type, message.from_user.id)
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    if message.from_user.id == ADMIN_ID:
        kb.add(
            types.InlineKeyboardButton("📢 Reklama yuborish", callback_data="admin_broadcast"),
            types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats")
        )
    
    await message.answer(f"<b>Salom {message.from_user.first_name}!</b> 👋\nBot ishlamoqda!", reply_markup=kb)

# --- BOTNI ISHGA TUSHIRISH ---
async def on_startup(dp):
    logger.info("Bot muvaffaqiyatli ishga tushdi!")

async def handle(request):
    return web.Response(text="Bot is online! 🚀")

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 8080))
    app = web.Application()
    app.router.add_get("/", handle)
    
    # Botni polling rejimida ishga tushiramiz
    loop = asyncio.get_event_loop()
    loop.create_task(dp.start_polling(on_startup=on_startup))
    web.run_app(app, host="0.0.0.0", port=port)
