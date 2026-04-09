import logging
import sqlite3
import io
import asyncio
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.utils import executor, exceptions
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton

# --- KONFIGURATSIYA ---
API_TOKEN = '7732017441:AAF-sL-zc0-AaR6r1XltVh851_23TpxGlQA'
ADMIN_ID = 7339714216  # Sizning ID

logging.basicConfig(level=logging.INFO)
storage = MemoryStorage()
bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot, storage=storage)

# --- BAZA MANTIQI ---
class Database:
    def __init__(self, db_name='pro_adv_bot.db'):
        self.conn = sqlite3.connect(db_name)
        self.cursor = self.conn.cursor()
        self.create_tables()

    def create_tables(self):
        self.cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, join_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP)')
        self.cursor.execute('CREATE TABLE IF NOT EXISTS chats (chat_id INTEGER PRIMARY KEY, title TEXT, type TEXT, added_by INTEGER)')
        self.conn.commit()

    def add_user(self, user_id):
        self.cursor.execute('INSERT OR IGNORE INTO users (user_id) VALUES (?)', (user_id,))
        self.conn.commit()

    def add_chat(self, chat_id, title, c_type, user_id):
        self.cursor.execute('INSERT OR REPLACE INTO chats VALUES (?, ?, ?, ?)', (chat_id, title, c_type, user_id))
        self.conn.commit()

    def remove_chat(self, chat_id):
        self.cursor.execute('DELETE FROM chats WHERE chat_id = ?', (chat_id,))
        self.conn.commit()

db = Database()

# --- FSM (HOLATLAR) ---
class AdStates(StatesGroup):
    waiting_for_ad_content = State()
    waiting_for_buttons = State()
    confirm_send = State()

# --- ADMIN KLAVIATURASI ---
def get_admin_kb():
    kb = InlineKeyboardMarkup(row_width=2)
    kb.add(
        InlineKeyboardButton("📢 Global Reklama", callback_data="admin_broadcast"),
        InlineKeyboardButton("📊 Statistika", callback_data="admin_stats"),
        InlineKeyboardButton("📂 Guruhlar Fayli", callback_data="admin_file"),
        InlineKeyboardButton("🧹 Tozalash", callback_data="admin_cleanup")
    )
    return kb

# --- ASOSIY HANDLERLAR ---

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    db.add_user(message.from_user.id)
    text = "<b>Assalomu alaykum, Professional Reklama Botiga xush kelibsiz!</b> 💎\n\n"
    if message.from_user.id == ADMIN_ID:
        text += "Siz bot adminisiz. Boshqaruv panelidan foydalanishingiz mumkin 👇"
        await message.answer(text, reply_markup=get_admin_kb())
    else:
        await message.answer(text + "Botni guruhlarga qo'shing va reklama imkoniyatlaridan foydalaning.")

# Botni guruhga qo'shganda/chiqarganda
@dp.my_chat_member_handler()
async def chat_m_handler(update: types.ChatMemberUpdated):
    if update.new_chat_member.status in ['administrator', 'member']:
        db.add_chat(update.chat.id, update.chat.title, update.chat.type, update.from_user.id)
    elif update.new_chat_member.status in ['left', 'kicked']:
        db.db.remove_chat(update.chat.id)

# --- REKLAMA YARATISH (FSM) ---

@dp.callback_query_handler(text="admin_broadcast", user_id=ADMIN_ID)
async def start_broadcast(call: types.CallbackQuery):
    await call.message.answer("Reklama matnini yoki rasm/video yuboring: \n(Bekor qilish uchun /cancel)")
    await AdStates.waiting_for_ad_content.set()

@dp.message_handler(state=AdStates.waiting_for_ad_content, content_types=types.ContentTypes.ANY)
async def get_content(message: types.Message, state: FSMContext):
    await state.update_data(message_id=message.message_id, chat_id=message.chat.id)
    await message.answer("Tugmalar qo'shasizmi? Format: <code>Nom - Link</code>\nHar bir tugmani yangi qatordan yozing. Yo'q bo'lsa 'Xayr' deb yozing.")
    await AdStates.waiting_for_buttons.set()

@dp.message_handler(state=AdStates.waiting_for_buttons)
async def get_buttons(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup()
    if message.text.lower() != 'xayr':
        lines = message.text.split('\n')
        for line in lines:
            try:
                name, url = line.split('-')
                kb.add(InlineKeyboardButton(text=name.strip(), url=url.strip()))
            except:
                continue
    
    await state.update_data(buttons=kb)
    data = await state.get_data()
    await message.answer("Reklama tayyor. Uni hamma joyga yuboramizmi?", reply_markup=InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Ha, yuborilsin", callback_data="confirm_yes"),
        InlineKeyboardButton("❌ Yo'q", callback_data="confirm_no")
    ))
    await AdStates.confirm_send.set()

@dp.callback_query_handler(state=AdStates.confirm_send)
async def final_step(call: types.CallbackQuery, state: FSMContext):
    if call.data == "confirm_yes":
        data = await state.get_data()
        db.cursor.execute("SELECT chat_id FROM chats")
        chats = db.cursor.fetchall()
        db.cursor.execute("SELECT user_id FROM users")
        users = db.cursor.fetchall()
        
        targets = list(set([c[0] for c in chats] + [u[0] for u in users]))
        
        count = 0
        await call.message.answer(f"🚀 Reklama {len(targets)} ta manzilga yuborilmoqda...")
        
        for tid in targets:
            try:
                await bot.copy_message(tid, data['chat_id'], data['message_id'], reply_markup=data['buttons'])
                count += 1
                await asyncio.sleep(0.05) # Flood himoyasi
            except exceptions.BotBlocked: continue
            except exceptions.ChatNotFound: continue
            except: continue
            
        await call.message.answer(f"✅ Tayyor! {count} ta manzilga yetkazildi.")
    else:
        await call.message.answer("Reklama bekor qilindi.")
    
    await state.finish()

# --- STATISTIKA VA FILER ---

@dp.callback_query_handler(text="admin_stats", user_id=ADMIN_ID)
async def admin_stats(call: types.CallbackQuery):
    db.cursor.execute("SELECT COUNT(*) FROM users")
    u = db.cursor.fetchone()[0]
    db.cursor.execute("SELECT COUNT(*) FROM chats")
    c = db.cursor.fetchone()[0]
    await call.message.answer(f"📊 <b>Statistika:</b>\n\n👤 Userlar: {u}\n🏢 Chatlar: {c}")

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
