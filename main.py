import logging
import asyncio
import os
from typing import Dict, List, Set
from datetime import datetime

from aiogram import Bot, Dispatcher, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ContentType
)
from aiogram.utils.callback_data import CallbackData

import gspread
from google.oauth2.service_account import Credentials

from aiohttp import web

# ═══════════════════════════════════════════════════════════════
# KONFIGURATSIYA
# ═══════════════════════════════════════════════════════════════

BOT_TOKEN = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")
ADMIN_ID = int(os.getenv("ADMIN_ID", "123456789"))  # Admin Telegram ID
GOOGLE_CREDENTIALS_FILE = "credentials.json"
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "AdsManagerBot")
PORT = int(os.getenv("PORT", 8080))

# Logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════
# GOOGLE SHEETS BILAN ISHLASH
# ═══════════════════════════════════════════════════════════════

class GoogleSheetsDB:
    def __init__(self):
        self.sheet = None
        self.worksheet = None
        self._connect()
    
    def _connect(self):
        """Google Sheets'ga ulanish"""
        try:
            scopes = [
                '[googleapis.com](https://www.googleapis.com/auth/spreadsheets)',
                '[googleapis.com](https://www.googleapis.com/auth/drive)'
            ]
            
            creds = Credentials.from_service_account_file(
                GOOGLE_CREDENTIALS_FILE, 
                scopes=scopes
            )
            client = gspread.authorize(creds)
            
            # Spreadsheet'ni ochish yoki yaratish
            try:
                self.sheet = client.open(SPREADSHEET_NAME)
            except gspread.SpreadsheetNotFound:
                self.sheet = client.create(SPREADSHEET_NAME)
                logger.info(f"Yangi spreadsheet yaratildi: {SPREADSHEET_NAME}")
            
            # Sheet2 worksheet'ini ochish yoki yaratish
            try:
                self.worksheet = self.sheet.worksheet("Sheet2")
            except gspread.WorksheetNotFound:
                self.worksheet = self.sheet.add_worksheet(
                    title="Sheet2", 
                    rows=1000, 
                    cols=10
                )
                # Sarlavhalarni qo'shish
                self.worksheet.update('A1:D1', [['user_id', 'channel_id', 'title', 'date']])
                logger.info("Sheet2 worksheet yaratildi")
            
            logger.info("Google Sheets'ga muvaffaqiyatli ulandi")
            
        except Exception as e:
            logger.error(f"Google Sheets ulanish xatosi: {e}")
            raise
    
    def add_channel(self, user_id: int, channel_id: int, title: str) -> bool:
        """Yangi kanal qo'shish"""
        try:
            # Mavjudligini tekshirish
            existing = self.get_channel(user_id, channel_id)
            if existing:
                return False
            
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.worksheet.append_row([str(user_id), str(channel_id), title, date])
            logger.info(f"Kanal qo'shildi: {title} ({channel_id}) - User: {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Kanal qo'shish xatosi: {e}")
            return False
    
    def get_channel(self, user_id: int, channel_id: int) -> dict:
        """Bitta kanalni olish"""
        try:
            records = self.worksheet.get_all_records()
            for record in records:
                if str(record.get('user_id')) == str(user_id) and \
                   str(record.get('channel_id')) == str(channel_id):
                    return record
            return None
        except Exception as e:
            logger.error(f"Kanal olish xatosi: {e}")
            return None
    
    def get_user_channels(self, user_id: int) -> List[dict]:
        """Foydalanuvchining kanallarini olish"""
        try:
            records = self.worksheet.get_all_records()
            return [r for r in records if str(r.get('user_id')) == str(user_id)]
        except Exception as e:
            logger.error(f"Foydalanuvchi kanallarini olish xatosi: {e}")
            return []
    
    def get_all_channels(self) -> List[dict]:
        """Barcha kanallarni olish (Admin uchun)"""
        try:
            records = self.worksheet.get_all_records()
            return records
        except Exception as e:
            logger.error(f"Barcha kanallarni olish xatosi: {e}")
            return []
    
    def delete_channel(self, user_id: int, channel_id: int) -> bool:
        """Kanalni o'chirish"""
        try:
            records = self.worksheet.get_all_records()
            for i, record in enumerate(records, start=2):  # 2 dan boshlanadi (sarlavha 1-qator)
                if str(record.get('user_id')) == str(user_id) and \
                   str(record.get('channel_id')) == str(channel_id):
                    self.worksheet.delete_rows(i)
                    logger.info(f"Kanal o'chirildi: {channel_id}")
                    return True
            return False
        except Exception as e:
            logger.error(f"Kanal o'chirish xatosi: {e}")
            return False
    
    def get_stats(self) -> dict:
        """Statistika olish"""
        try:
            records = self.worksheet.get_all_records()
            users = set(r.get('user_id') for r in records)
            return {
                'total_channels': len(records),
                'total_users': len(users),
                'channels': records
            }
        except Exception as e:
            logger.error(f"Statistika olish xatosi: {e}")
            return {'total_channels': 0, 'total_users': 0, 'channels': []}


# ═══════════════════════════════════════════════════════════════
# FSM HOLATLAR
# ═══════════════════════════════════════════════════════════════

class AddChannelStates(StatesGroup):
    waiting_for_forward = State()


class SendAdStates(StatesGroup):
    selecting_channels = State()
    waiting_for_content = State()
    confirm_send = State()


# ═══════════════════════════════════════════════════════════════
# CALLBACK DATA
# ═══════════════════════════════════════════════════════════════

channel_cb = CallbackData("channel", "action", "channel_id")


# ═══════════════════════════════════════════════════════════════
# BOT INITIALIZATSIYA
# ═══════════════════════════════════════════════════════════════

bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# Google Sheets DB
db = GoogleSheetsDB()

# Tanlangan kanallarni saqlash (user_id -> set of channel_ids)
user_selections: Dict[int, Set[int]] = {}


# ═══════════════════════════════════════════════════════════════
# YORDAMCHI FUNKSIYALAR
# ═══════════════════════════════════════════════════════════════

def get_main_menu(user_id: int) -> ReplyKeyboardMarkup:
    """Asosiy menyu klaviaturasi"""
    keyboard = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    keyboard.add(
        KeyboardButton("➕ Kanal qo'shish"),
        KeyboardButton("📢 Reklama yuborish")
    )
    
    # Admin uchun qo'shimcha tugmalar
    if user_id == ADMIN_ID:
        keyboard.add(KeyboardButton("📊 Statistika"))
    
    return keyboard


def get_channels_keyboard(user_id: int, selected: Set[int]) -> InlineKeyboardMarkup:
    """Kanallar tanlash klaviaturasi"""
    keyboard = InlineKeyboardMarkup(row_width=1)
    
    # Admin barcha kanallarni ko'radi
    if user_id == ADMIN_ID:
        channels = db.get_all_channels()
    else:
        channels = db.get_user_channels(user_id)
    
    if not channels:
        return None
    
    # Dublikatlarni olib tashlash
    seen_channels = set()
    unique_channels = []
    for ch in channels:
        ch_id = int(ch.get('channel_id', 0))
        if ch_id not in seen_channels:
            seen_channels.add(ch_id)
            unique_channels.append(ch)
    
    for channel in unique_channels:
        channel_id = int(channel.get('channel_id', 0))
        title = channel.get('title', 'Nomsiz kanal')
        
        # Toggle belgisi
        if channel_id in selected:
            emoji = "🟢"
        else:
            emoji = "⚪"
        
        keyboard.add(InlineKeyboardButton(
            text=f"{emoji} {title}",
            callback_data=channel_cb.new(action="toggle", channel_id=str(channel_id))
        ))
    
    # Tasdiqlash tugmasi
    keyboard.add(InlineKeyboardButton(
        text="✅ Tanladim",
        callback_data=channel_cb.new(action="confirm", channel_id="0")
    ))
    
    # Bekor qilish tugmasi
    keyboard.add(InlineKeyboardButton(
        text="❌ Bekor qilish",
        callback_data=channel_cb.new(action="cancel", channel_id="0")
    ))
    
    return keyboard


# ═══════════════════════════════════════════════════════════════
# HANDLERLAR
# ═══════════════════════════════════════════════════════════════

@dp.message_handler(commands=['start'], state='*')
async def cmd_start(message: types.Message, state: FSMContext):
    """Start buyrug'i"""
    await state.finish()
    
    user_name = message.from_user.first_name or "Foydalanuvchi"
    
    welcome_text = f"""
🎉 <b>Xush kelibsiz, {user_name}!</b>

🤖 Men <b>Professional Reklama Menejeri</b> botiman.

📋 <b>Imkoniyatlar:</b>
• Kanallaringizni qo'shing
• Premium emoji va formatlash bilan reklamalar yuborin
• Bir nechta kanallarga bir vaqtda post qiling

⬇️ Quyidagi menyudan foydalaning:
"""
    
    await message.answer(
        welcome_text,
        reply_markup=get_main_menu(message.from_user.id)
    )


@dp.message_handler(lambda m: m.text == "➕ Kanal qo'shish", state='*')
async def add_channel_start(message: types.Message, state: FSMContext):
    """Kanal qo'shish jarayonini boshlash"""
    await state.finish()
    
    instruction = """
📢 <b>Kanal qo'shish</b>

Kanal qo'shish uchun:

1️⃣ Botni kanalingizga <b>admin</b> sifatida qo'shing
2️⃣ Kanaldan istalgan xabarni menga <b>forward</b> qiling

⚠️ <i>Eslatma: Bot kanaldagi xabarlarni yuborish uchun admin bo'lishi shart!</i>
"""
    
    await message.answer(instruction)
    await AddChannelStates.waiting_for_forward.set()


@dp.message_handler(
    content_types=[ContentType.ANY],
    state=AddChannelStates.waiting_for_forward
)
async def process_forwarded_channel(message: types.Message, state: FSMContext):
    """Forward qilingan xabarni qayta ishlash"""
    
    # Forward xabar tekshiruvi
    if not message.forward_from_chat:
        await message.answer(
            "❌ Iltimos, kanaldan xabarni <b>forward</b> qiling!\n\n"
            "Kanal xabarini menga uzating.",
            parse_mode=types.ParseMode.HTML
        )
        return
    
    chat = message.forward_from_chat
    
    # Kanal ekanligini tekshirish
    if chat.type != 'channel':
        await message.answer(
            "❌ Bu kanal emas!\n\n"
            "Iltimos, <b>kanal</b>dan xabar forward qiling.",
            parse_mode=types.ParseMode.HTML
        )
        return
    
    channel_id = chat.id
    channel_title = chat.title or "Nomsiz kanal"
    user_id = message.from_user.id
    
    # Botning admin ekanligini tekshirish
    try:
        bot_member = await bot.get_chat_member(channel_id, bot.id)
        if bot_member.status not in ['administrator', 'creator']:
            await message.answer(
                f"⚠️ Bot <b>{channel_title}</b> kanalida admin emas!\n\n"
                "Iltimos, avval botni kanalga admin qilib qo'shing.",
                parse_mode=types.ParseMode.HTML
            )
            return
    except Exception as e:
        logger.warning(f"Admin tekshirish xatosi: {e}")
        await message.answer(
            f"⚠️ Bot <b>{channel_title}</b> kanalida admin emas!\n\n"
            "Iltimos, avval botni kanalga admin qilib qo'shing.",
            parse_mode=types.ParseMode.HTML
        )
        return
    
    # Bazaga qo'shish
    success = db.add_channel(user_id, channel_id, channel_title)
    
    if success:
        await message.answer(
            f"✅ Kanal muvaffaqiyatli qo'shildi!\n\n"
            f"📢 <b>{channel_title}</b>\n"
            f"🆔 <code>{channel_id}</code>",
            reply_markup=get_main_menu(user_id),
            parse_mode=types.ParseMode.HTML
        )
    else:
        await message.answer(
            f"ℹ️ Bu kanal allaqachon qo'shilgan!\n\n"
            f"📢 <b>{channel_title}</b>",
            reply_markup=get_main_menu(user_id),
            parse_mode=types.ParseMode.HTML
        )
    
    await state.finish()


@dp.message_handler(lambda m: m.text == "📢 Reklama yuborish", state='*')
async def send_ad_start(message: types.Message, state: FSMContext):
    """Reklama yuborish jarayonini boshlash"""
    await state.finish()
    
    user_id = message.from_user.id
    user_selections[user_id] = set()
    
    keyboard = get_channels_keyboard(user_id, user_selections[user_id])
    
    if not keyboard:
        await message.answer(
            "📭 Sizda hali kanallar yo'q!\n\n"
            "Avval <b>➕ Kanal qo'shish</b> tugmasini bosing.",
            parse_mode=types.ParseMode.HTML
        )
        return
    
    await message.answer(
        "📋 <b>Kanallarni tanlang</b>\n\n"
        "⚪ - Tanlanmagan\n"
        "🟢 - Tanlangan\n\n"
        "Tanlash uchun kanal nomini bosing:",
        reply_markup=keyboard,
        parse_mode=types.ParseMode.HTML
    )
    
    await SendAdStates.selecting_channels.set()


@dp.callback_query_handler(
    channel_cb.filter(action="toggle"),
    state=SendAdStates.selecting_channels
)
async def toggle_channel_selection(
    callback: types.CallbackQuery,
    callback_data: dict,
    state: FSMContext
):
    """Kanal tanlovini o'zgartirish"""
    user_id = callback.from_user.id
    channel_id = int(callback_data['channel_id'])
    
    if user_id not in user_selections:
        user_selections[user_id] = set()
    
    # Toggle
    if channel_id in user_selections[user_id]:
        user_selections[user_id].discard(channel_id)
    else:
        user_selections[user_id].add(channel_id)
    
    # Klaviaturani yangilash (miltillamasdan)
    new_keyboard = get_channels_keyboard(user_id, user_selections[user_id])
    
    try:
        await callback.message.edit_reply_markup(reply_markup=new_keyboard)
    except Exception as e:
        logger.warning(f"Klaviatura yangilash xatosi: {e}")
    
    await callback.answer()


@dp.callback_query_handler(
    channel_cb.filter(action="confirm"),
    state=SendAdStates.selecting_channels
)
async def confirm_channel_selection(
    callback: types.CallbackQuery,
    callback_data: dict,
    state: FSMContext
):
    """Kanal tanlovini tasdiqlash"""
    user_id = callback.from_user.id
    
    selected = user_selections.get(user_id, set())
    
    if not selected:
        await callback.answer("⚠️ Kamida bitta kanal tanlang!", show_alert=True)
        return
    
    # Tanlangan kanallarni FSM-ga saqlash
    await state.update_data(selected_channels=list(selected))
    
    # Kanal nomlarini olish
    if user_id == ADMIN_ID:
        all_channels = db.get_all_channels()
    else:
        all_channels = db.get_user_channels(user_id)
    
    channel_names = []
    for ch in all_channels:
        if int(ch.get('channel_id', 0)) in selected:
            channel_names.append(ch.get('title', 'Nomsiz'))
    
    await callback.message.edit_text(
        f"✅ <b>Tanlangan kanallar ({len(selected)} ta):</b>\n\n"
        + "\n".join(f"• {name}" for name in channel_names) +
        "\n\n📝 Endi reklama kontentini yuboring:\n"
        "<i>(Rasm, Video yoki Matn)</i>",
        parse_mode=types.ParseMode.HTML
    )
    
    await SendAdStates.waiting_for_content.set()
    await callback.answer()


@dp.callback_query_handler(
    channel_cb.filter(action="cancel"),
    state=SendAdStates.selecting_channels
)
async def cancel_channel_selection(
    callback: types.CallbackQuery,
    callback_data: dict,
    state: FSMContext
):
    """Kanal tanlovini bekor qilish"""
    user_id = callback.from_user.id
    user_selections.pop(user_id, None)
    
    await callback.message.edit_text("❌ Bekor qilindi.")
    await state.finish()
    await callback.answer()


@dp.message_handler(
    content_types=[
        ContentType.TEXT,
        ContentType.PHOTO,
        ContentType.VIDEO,
        ContentType.ANIMATION,
        ContentType.DOCUMENT,
        ContentType.AUDIO,
        ContentType.VOICE,
        ContentType.VIDEO_NOTE,
        ContentType.STICKER
    ],
    state=SendAdStates.waiting_for_content
)
async def receive_ad_content(message: types.Message, state: FSMContext):
    """Reklama kontentini qabul qilish"""
    user_id = message.from_user.id
    data = await state.get_data()
    selected_channels = data.get('selected_channels', [])
    
    if not selected_channels:
        await message.answer(
            "❌ Xatolik yuz berdi. Qaytadan boshlang.",
            reply_markup=get_main_menu(user_id)
        )
        await state.finish()
        return
    
    # Xabarni saqlash
    await state.update_data(ad_message_id=message.message_id, ad_chat_id=message.chat.id)
    
    # Tasdiqlash klaviaturasi
    confirm_keyboard = InlineKeyboardMarkup(row_width=2)
    confirm_keyboard.add(
        InlineKeyboardButton("✅ Yuborish", callback_data="send_ad_confirm"),
        InlineKeyboardButton("❌ Bekor qilish", callback_data="send_ad_cancel")
    )
    
    await message.answer(
        f"📋 <b>Tasdiqlash</b>\n\n"
        f"Yuqoridagi kontent <b>{len(selected_channels)}</b> ta kanalga yuboriladi.\n\n"
        "Davom etasizmi?",
        reply_markup=confirm_keyboard,
        parse_mode=types.ParseMode.HTML
    )
    
    await SendAdStates.confirm_send.set()


@dp.callback_query_handler(
    lambda c: c.data == "send_ad_confirm",
    state=SendAdStates.confirm_send
)
async def confirm_send_ad(callback: types.CallbackQuery, state: FSMContext):
    """Reklamani yuborishni tasdiqlash"""
    user_id = callback.from_user.id
    data = await state.get_data()
    
    selected_channels = data.get('selected_channels', [])
    ad_message_id = data.get('ad_message_id')
    ad_chat_id = data.get('ad_chat_id')
    
    if not selected_channels or not ad_message_id:
        await callback.message.edit_text("❌ Xatolik yuz berdi.")
        await state.finish()
        return
    
    await callback.message.edit_text("⏳ Yuborilmoqda...")
    
    success_count = 0
    fail_count = 0
    failed_channels = []
    
    for channel_id in selected_channels:
        try:
            # send_copy - barcha formatlashlar va premium emojilar saqlanadi
            await bot.copy_message(
                chat_id=channel_id,
                from_chat_id=ad_chat_id,
                message_id=ad_message_id
            )
            success_count += 1
            await asyncio.sleep(0.5)  # Rate limit
            
        except Exception as e:
            logger.error(f"Xabar yuborish xatosi ({channel_id}): {e}")
            fail_count += 1
            failed_channels.append(str(channel_id))
    
    # Natija
    result_text = f"""
✅ <b>Reklama yuborildi!</b>

📊 <b>Natijalar:</b>
• Muvaffaqiyatli: <b>{success_count}</b>
• Muvaffaqiyatsiz: <b>{fail_count}</b>
"""
    
    if failed_channels:
        result_text += f"\n⚠️ Xato bo'lgan kanallar: {', '.join(failed_channels)}"
    
    await callback.message.edit_text(result_text, parse_mode=types.ParseMode.HTML)
    
    # Tozalash
    user_selections.pop(user_id, None)
    await state.finish()


@dp.callback_query_handler(
    lambda c: c.data == "send_ad_cancel",
    state=SendAdStates.confirm_send
)
async def cancel_send_ad(callback: types.CallbackQuery, state: FSMContext):
    """Reklamani yuborishni bekor qilish"""
    user_id = callback.from_user.id
    user_selections.pop(user_id, None)
    
    await callback.message.edit_text(
        "❌ Reklama yuborish bekor qilindi.",
        parse_mode=types.ParseMode.HTML
    )
    await state.finish()


@dp.message_handler(lambda m: m.text == "📊 Statistika", state='*')
async def show_stats(message: types.Message, state: FSMContext):
    """Statistika ko'rsatish (Faqat Admin)"""
    await state.finish()
    
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Bu funksiya faqat admin uchun!")
        return
    
    stats = db.get_stats()
    
    stats_text = f"""
📊 <b>Bot Statistikasi</b>

👥 Jami foydalanuvchilar: <b>{stats['total_users']}</b>
📢 Jami kanallar: <b>{stats['total_channels']}</b>
"""
    
    # So'nggi 5 ta kanal
    channels = stats.get('channels', [])[-5:]
    if channels:
        stats_text += "\n📋 <b>So'nggi qo'shilgan kanallar:</b>\n"
        for ch in reversed(channels):
            stats_text += f"• {ch.get('title', 'Nomsiz')} - {ch.get('date', '')}\n"
    
    await message.answer(stats_text, parse_mode=types.ParseMode.HTML)


@dp.message_handler(commands=['cancel'], state='*')
async def cmd_cancel(message: types.Message, state: FSMContext):
    """Barcha holatlarni bekor qilish"""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer(
            "Bekor qilinadigan jarayon yo'q.",
            reply_markup=get_main_menu(message.from_user.id)
        )
        return
    
    user_selections.pop(message.from_user.id, None)
    await state.finish()
    await message.answer(
        "✅ Jarayon bekor qilindi.",
        reply_markup=get_main_menu(message.from_user.id)
    )


# ═══════════════════════════════════════════════════════════════
# WEB SERVER (Render.com uchun)
# ═══════════════════════════════════════════════════════════════

async def handle_health(request):
    """Health check endpoint"""
    return web.Response(text="OK", status=200)


async def handle_root(request):
    """Root endpoint"""
    return web.Response(
        text="🤖 Ads Manager Bot is running!",
        status=200
    )


async def start_web_server():
    """Web serverni ishga tushirish"""
    app = web.Application()
    app.router.add_get('/', handle_root)
    app.router.add_get('/health', handle_health)
    
    runner = web.AppRunner(app)
    await runner.setup()
    
    site = web.TCPSite(runner, '0.0.0.0', PORT)
    await site.start()
    
    logger.info(f"Web server ishga tushdi: http://0.0.0.0:{PORT}")


# ═══════════════════════════════════════════════════════════════
# ASOSIY FUNKSIYA
# ═══════════════════════════════════════════════════════════════

async def on_startup():
    """Bot ishga tushganda"""
    logger.info("Bot ishga tushmoqda...")
    
    # Web serverni ishga tushirish
    await start_web_server()
    
    # Bot ma'lumotlarini olish
    bot_info = await bot.get_me()
    logger.info(f"Bot: @{bot_info.username} ({bot_info.id})")


async def on_shutdown():
    """Bot to'xtaganda"""
    logger.info("Bot to'xtamoqda...")
    await dp.storage.close()
    await dp.storage.wait_closed()
    session = await bot.get_session()
    await session.close()


async def main():
    """Asosiy funksiya"""
    try:
        await on_startup()
        await dp.start_polling(
            reset_webhook=True,
            skip_updates=True
        )
    finally:
        await on_shutdown()


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("Bot to'xtatildi")
