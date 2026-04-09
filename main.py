import os
import asyncio
import logging
import gspread
from oauth2client.service_account import ServiceAccountCredentials
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiohttp import web

# --- KONFIGURATSIYA ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 0))
SPREADSHEET_ID = "175HMek0SGGy9u6xKzpdVlbJmppRksKonxSjZNVUA2lQ"

# Logging sozlamalari
logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot)

# --- GOOGLE SHEETS BILAN ISHLASH ---
def get_sheets():
    """Google Sheets API-ga ulanish"""
    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
    # credentials.json fayli root papkada bo'lishi shart
    creds = ServiceAccountCredentials.from_json_keyfile_name('credentials.json', scope)
    client = gspread.authorize(creds)
    return client.open_by_key(SPREADSHEET_ID).sheet1

def log_to_sheet(chat_id, title, chat_type, user_id):
    """Ma'lumotlarni jadvalga yozish"""
    try:
        sheet = get_sheets()
        ids = sheet.col_values(1)
        if str(chat_id) not in ids:
            sheet.append_row([str(chat_id), str(title), str(chat_type), str(user_id)])
            logging.info(f"Yangi yozuv qo'shildi: {title}")
    except Exception as e:
        logging.error(f"Google Sheets bilan xatolik: {e}")

# --- BOT HANDLERLARI ---

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    """/start buyrug'i va foydalanuvchini ro'yxatga olish"""
    log_to_sheet(message.from_user.id, message.from_user.full_name, "USER", message.from_user.id)
    
    welcome_text = (
        f"Salom {message.from_user.first_name}! <tg-emoji id='5432490150935534230'>✨</tg-emoji>\n"
        "Professional reklama botiga xush kelibsiz.\n\n"
        "Bot barcha guruh va kanallarni avtomatik jadvalga yozib boradi."
    )
    
    kb = types.InlineKeyboardMarkup()
    if message.from_user.id == ADMIN_ID:
        kb.add(types.InlineKeyboardButton("📢 Reklama yuborish", callback_data="admin_broadcast"))
        kb.add(types.InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"))
        
    await message.answer(welcome_text, reply_markup=kb)

@dp.my_chat_member_handler()
async def on_bot_added(update: types.ChatMemberUpdated):
    """Bot guruh yoki kanalga qo'shilganda ishlaydi"""
    if update.new_chat_member.status in ['administrator', 'member']:
        chat_title = update.chat.title or update.chat.full_name
        log_to_sheet(update.chat.id, chat_title, update.chat.type, update.from_user.id)

# --- ADMIN REKLAMA TIZIMI ---

@dp.callback_query_handler(text="admin_broadcast", user_id=ADMIN_ID)
async def ask_ad(call: types.CallbackQuery):
    await call.message.answer("Reklama xabaringizni yuboring (Matn, Rasm, Video yoki Sticker).\nUni barcha manzillarga yuboraman!")

@dp.message_handler(user_id=ADMIN_ID, content_types=types.ContentTypes.ANY)
async def start_broadcast(message: types.Message):
    if message.text == "/start": return # Startni reklama qilmaslik uchun

    sheet = get_sheets()
    targets = sheet.col_values(1)[1:] # Sarlavhadan keyingi barcha ID'lar
    
    await message.answer(f"🚀 Tarqatish boshlandi: {len(targets)} ta manzilga...")
    
    success = 0
    for tid in targets:
        try:
            # Har qanday turdagi xabarni nusxalash (copy_message)
            await bot.copy_message(chat_id=tid, from_chat_id=message.chat.id, message_id=message.message_id)
            success += 1
            await asyncio.sleep(0.05) # Flood himoyasi
        except Exception:
            continue
            
    await message.answer(f"✅ Tarqatish tugadi.\nMuallafaqiyatli: {success} ta.")

@dp.callback_query_handler(text="admin_stats", user_id=ADMIN_ID)
async def show_stats(call: types.CallbackQuery):
    sheet = get_sheets()
    count = len(sheet.col_values(1)) - 1
    await call.answer(f"Jami manzillar: {count} ta", show_alert=True)

# --- RENDER WEB SERVER (Uyg'oq tutish uchun) ---

async def handle(request):
    """Web-serverga so'rov kelganda javob berish"""
    return web.Response(text="Bot is running! 🚀")

async def on_startup(dispatcher):
    logging.info("Bot ishga tushirildi!")

# --- ISHGA TUSHIRISH ---

if __name__ == '__main__':
    # Render beradigan portni olish
    port = int(os.environ.get("PORT", 8080))
    
    # Web App yaratish
    app = web.Application()
    app.router.add_get("/", handle)
    
    # Botni polling rejimida ishga tushirish (web server bilan parallel)
    loop = asyncio.get_event_loop()
    loop.create_task(dp.start_polling())
    
    # Web serverni ishga tushirish
    web.run_app(app, host="0.0.0.0", port=port)
