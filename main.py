import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.utils import executor
from aiogram.dispatcher import FSMContext
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiohttp import web

# --- CONFIG ---
API_TOKEN = os.getenv('BOT_TOKEN')
ADMIN_ID = int(os.getenv('ADMIN_ID', 7339714216))

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN, parse_mode=types.ParseMode.HTML)
storage = MemoryStorage()
dp = Dispatcher(bot, storage=storage)

# --- STATES (Holatlar) ---
class AdStates(StatesGroup):
    waiting_for_channel = State()
    selecting_channels = State()
    waiting_for_media = State()
    waiting_for_text = State()
    waiting_for_btn_name = State()
    waiting_for_btn_url = State()
    confirm_ad = State()

# Foydalanuvchi kanallari (Vaqtincha xotira, buni keyinchalik Sheetsga ulash mumkin)
# {user_id: {channel_id: "Channel Title"}}
user_channels = {}

# --- KEYBOARDS ---
def main_menu(user_id):
    kb = types.ReplyKeyboardMarkup(resize_keyboard=True)
    kb.row("➕ Kanal qo'shish", "📢 Reklama yuborish")
    kb.row("📊 Statistika", "❓ Yordam")
    return kb

# --- HANDLERS ---

@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    await message.answer(f"👋 Salom {message.from_user.first_name}!\nReklama menejeri botiga xush kelibsiz.", 
                         reply_markup=main_menu(message.from_user.id))

# 1. KANAL QO'SHISH
@dp.message_handler(text="➕ Kanal qo'shish")
async def add_channel_start(message: types.Message):
    await message.answer("📢 Kanalni qo'shish uchun:\n1. Botni kanalda <b>Admin</b> qiling.\n2. Kanaldan bitta xabarni menga <b>Forward</b> qiling.")
    await AdStates.waiting_for_channel.set()

@dp.message_handler(state=AdStates.waiting_for_channel, is_forwarded=True, content_types=types.ContentTypes.ANY)
async def process_channel_add(message: types.Message, state: FSMContext):
    if message.forward_from_chat:
        chat = message.forward_from_chat
        uid = message.from_user.id
        
        if uid not in user_channels: user_channels[uid] = {}
        user_channels[uid][chat.id] = chat.title
        
        await message.answer(f"✅ Kanal qo'shildi: <b>{chat.title}</b>", reply_markup=main_menu(uid))
        await state.finish()
    else:
        await message.answer("❌ Bu kanal emas. Iltimos, kanaldan xabar uzating.")

# 2. REKLAMA YUBORISH (KANAL TANLASH)
@dp.message_handler(text="📢 Reklama yuborish")
async def start_ad(message: types.Message, state: FSMContext):
    uid = message.from_user.id
    if uid not in user_channels or not user_channels[uid]:
        return await message.answer("🤷‍♂️ Avval kanal qo'shishingiz kerak.")
    
    kb = types.InlineKeyboardMarkup(row_width=1)
    for cid, title in user_channels[uid].items():
        kb.add(types.InlineKeyboardButton(f"❌ {title}", callback_data=f"select_{cid}"))
    kb.add(types.InlineKeyboardButton("✅ Tanladim", callback_data="channels_done"))
    
    await message.answer("📍 Reklama yubormoqchi bo'lgan kanallaringizni tanlang:", reply_markup=kb)
    await state.update_data(selected_channels=[])
    await AdStates.selecting_channels.set()

@dp.callback_query_handler(lambda c: c.data.startswith('select_'), state=AdStates.selecting_channels)
async def toggle_channel(call: types.CallbackQuery, state: FSMContext):
    cid = int(call.data.split('_')[1])
    data = await state.get_data()
    selected = data.get('selected_channels', [])
    
    if cid in selected: selected.remove(cid)
    else: selected.append(cid)
    
    await state.update_data(selected_channels=selected)
    
    # Tugmalarni yangilash (Yashil belgi qo'yish)
    kb = types.InlineKeyboardMarkup(row_width=1)
    for ch_id, title in user_channels[call.from_user.id].items():
        mark = "✅" if ch_id in selected else "❌"
        kb.add(types.InlineKeyboardButton(f"{mark} {title}", callback_data=f"select_{ch_id}"))
    kb.add(types.InlineKeyboardButton("🚀 Tanladim", callback_data="channels_done"))
    
    await call.message.edit_reply_markup(reply_markup=kb)

@dp.callback_query_handler(text="channels_done", state=AdStates.selecting_channels)
async def channels_selected(call: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    if not data.get('selected_channels'):
        return await call.answer("⚠️ Kamida bitta kanal tanlang!", show_alert=True)
    
    await call.message.answer("🖼 Endi rasm yoki video yuboring (yoki /skip):")
    await AdStates.waiting_for_media.set()

# 3. KONTENT YIG'ISH
@dp.message_handler(state=AdStates.waiting_for_media, content_types=[types.ContentType.PHOTO, types.ContentType.VIDEO, types.ContentType.TEXT])
async def process_media(message: types.Message, state: FSMContext):
    if message.photo:
        await state.update_data(file_id=message.photo[-1].file_id, file_type='photo')
    elif message.video:
        await state.update_data(file_id=message.video.file_id, file_type='video')
    
    await message.answer("✍️ Reklama matnini (tavsifini) yuboring:")
    await AdStates.waiting_for_text.set()

@dp.message_handler(state=AdStates.waiting_for_text)
async def process_text(message: types.Message, state: FSMContext):
    await state.update_data(ad_text=message.text)
    kb = types.InlineKeyboardMarkup().add(types.InlineKeyboardButton("➕ Tugma qo'shish", callback_data="add_btn"),
                                          types.InlineKeyboardButton("⏩ O'tkazib yuborish", callback_data="preview"))
    await message.answer("🔗 Reklamaga tugma qo'shasizmi?", reply_markup=kb)

@dp.callback_query_handler(text="add_btn", state=AdStates.waiting_for_text)
async def ask_btn_name(call: types.CallbackQuery):
    await call.message.answer("📝 Tugma nomini yuboring:")
    await AdStates.waiting_for_btn_name.set()

@dp.message_handler(state=AdStates.waiting_for_btn_name)
async def process_btn_name(message: types.Message, state: FSMContext):
    await state.update_data(btn_name=message.text)
    await message.answer("🔗 Tugma manzilini (URL) yuboring:")
    await AdStates.waiting_for_btn_url.set()

@dp.message_handler(state=AdStates.waiting_for_btn_url)
async def process_btn_url(message: types.Message, state: FSMContext):
    if not message.text.startswith('http'):
        return await message.answer("❌ Noto'g'ri URL. Link http yoki https bilan boshlanishi shart.")
    await state.update_data(btn_url=message.text)
    await show_preview(message, state)

async def show_preview(message, state):
    data = await state.get_data()
    text = data.get('ad_text')
    kb = types.InlineKeyboardMarkup()
    if data.get('btn_name'):
        kb.add(types.InlineKeyboardButton(data['btn_name'], url=data['btn_url']))
    
    await message.answer("🧐 Reklama ko'rinishi:")
    if data.get('file_type') == 'photo':
        await bot.send_photo(message.chat.id, data['file_id'], caption=text, reply_markup=kb)
    elif data.get('file_type') == 'video':
        await bot.send_video(message.chat.id, data['file_id'], caption=text, reply_markup=kb)
    else:
        await bot.send_message(message.chat.id, text, reply_markup=kb)
    
    confirm_kb = types.ReplyKeyboardMarkup(resize_keyboard=True).row("✅ Tasdiqlash", "❌ Bekor qilish")
    await message.answer("Reklamani tanlangan kanallarga yuboramizmi?", reply_markup=confirm_kb)
    await AdStates.confirm_ad.set()

@dp.message_handler(state=AdStates.confirm_ad, text="✅ Tasdiqlash")
async def final_send(message: types.Message, state: FSMContext):
    data = await state.get_data()
    channels = data.get('selected_channels')
    
    kb = types.InlineKeyboardMarkup()
    if data.get('btn_name'):
        kb.add(types.InlineKeyboardButton(data['btn_name'], url=data['btn_url']))

    success = 0
    for cid in channels:
        try:
            if data.get('file_type') == 'photo':
                await bot.send_photo(cid, data['file_id'], caption=data['ad_text'], reply_markup=kb)
            elif data.get('file_type') == 'video':
                await bot.send_video(cid, data['file_id'], caption=data['ad_text'], reply_markup=kb)
            else:
                await bot.send_message(cid, data['ad_text'], reply_markup=kb)
            success += 1
        except Exception as e:
            logging.error(f"Xato: {e}")

    await message.answer(f"🚀 Reklama {success} ta kanalga yuborildi!", reply_markup=main_menu(message.from_user.id))
    await state.finish()

# --- WEB SERVER ---
async def handle(request): return web.Response(text="Ads Bot Active 🔊")
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
