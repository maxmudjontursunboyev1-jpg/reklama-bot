import os
import json
import asyncio
import logging
from datetime import datetime
from typing import List, Dict, Set

import gspread
from google.oauth2.service_account import Credentials

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
from aiohttp import web


# ════════════════════════════════════════════════════
# 🧩 CONFIG
# ════════════════════════════════════════════════════

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "AdsManagerBot")
PORT = int(os.getenv("PORT", 8080))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ════════════════════════════════════════════════════
# 🧩 GOOGLE SHEETS CONNECTION
# ════════════════════════════════════════════════════

def get_google_credentials():
    scopes = [
        "[googleapis.com](https://www.googleapis.com/auth/spreadsheets)",
        "[googleapis.com](https://www.googleapis.com/auth/drive)"
    ]
    secret_path = "/etc/secrets/GOOGLE_CREDENTIALS"
    try:
        if os.path.exists(secret_path):
            creds = Credentials.from_service_account_file(secret_path, scopes=scopes)
            logger.info("Render Secret fayldan credential yuklandi ✅")
        else:
            creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
            logger.info("Lokal fayldan credential yuklandi ✅")
        return creds
    except Exception as e:
        logger.error(f"⚠️ Google credential yuklab bo‘lmadi: {e}")
        raise


class GoogleSheetsDB:
    def __init__(self):
        self.sheet = None
        self.worksheet = None
        self._connect()

    def _connect(self):
        creds = get_google_credentials()
        client = gspread.authorize(creds)

        try:
            self.sheet = client.open(SPREADSHEET_NAME)
            logger.info(f"Sheets topildi: {SPREADSHEET_NAME}")
        except gspread.SpreadsheetNotFound:
            self.sheet = client.create(SPREADSHEET_NAME)
            logger.info(f"Yangi Sheets yaratildi: {SPREADSHEET_NAME}")

        try:
            self.worksheet = self.sheet.worksheet("Sheet2")
        except gspread.WorksheetNotFound:
            self.worksheet = self.sheet.add_worksheet("Sheet2", 1000, 10)
            self.worksheet.update('A1:D1', [["user_id", "channel_id", "title", "date"]])
            logger.info("Sheet2 yaratildi va sarlavha qo‘shildi")

    def add_channel(self, user_id: int, channel_id: int, title: str):
        records = self.worksheet.get_all_records()
        for r in records:
            if str(r.get("channel_id")) == str(channel_id) and str(r.get("user_id")) == str(user_id):
                return False
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.worksheet.append_row([str(user_id), str(channel_id), title, now])
        return True

    def get_user_channels(self, user_id: int) -> List[dict]:
        return [r for r in self.worksheet.get_all_records() if str(r.get("user_id")) == str(user_id)]

    def get_all_channels(self) -> List[dict]:
        return self.worksheet.get_all_records()

    def get_stats(self):
        records = self.worksheet.get_all_records()
        users = set(r.get("user_id") for r in records)
        return {
            "total_channels": len(records),
            "total_users": len(users),
            "channels": records
        }


db = GoogleSheetsDB()

# ════════════════════════════════════════════════════
# 🧩 BOT INITIALIZATION
# ════════════════════════════════════════════════════

bot = Bot(token=BOT_TOKEN, parse_mode=types.ParseMode.HTML)
dp = Dispatcher(bot, storage=MemoryStorage())

channel_cb = CallbackData("ch", "action", "cid")
user_selections: Dict[int, Set[int]] = {}


# ════════════════════════════════════════════════════
# 🧩 FSM STATES
# ════════════════════════════════════════════════════

class AddChannel(StatesGroup):
    waiting_for_forward = State()


class SendAd(StatesGroup):
    selecting_channels = State()
    waiting_for_content = State()
    confirm_send = State()


# ════════════════════════════════════════════════════
# 🧩 HELPERS
# ════════════════════════════════════════════════════

def main_menu(uid: int):
    menu = ReplyKeyboardMarkup(resize_keyboard=True)
    menu.row("➕ Kanal qo'shish", "📢 Reklama yuborish")
    if uid == ADMIN_ID:
        menu.add("📊 Statistika")
    return menu


def channel_keyboard(uid: int, selected: Set[int]):
    chans = db.get_all_channels() if uid == ADMIN_ID else db.get_user_channels(uid)
    if not chans:
        return None
    kb = InlineKeyboardMarkup(row_width=1)
    for c in chans:
        cid = int(c["channel_id"])
        title = c["title"]
        mark = "🟢" if cid in selected else "⚪"
        kb.add(InlineKeyboardButton(f"{mark} {title}", callback_data=channel_cb.new("toggle", cid)))
    kb.add(InlineKeyboardButton("✅ Tanladim", callback_data=channel_cb.new("confirm", 0)))
    kb.add(InlineKeyboardButton("❌ Bekor qilish", callback_data=channel_cb.new("cancel", 0)))
    return kb


# ════════════════════════════════════════════════════
# 🧩 HANDLERS
# ════════════════════════════════════════════════════

@dp.message_handler(commands=["start"], state="*")
async def start_cmd(m: types.Message, state: FSMContext):
    await state.finish()
    await m.answer(
        f"👋 Salom, <b>{m.from_user.first_name}</b>!\n\nMen sizga kanallaringizga reklama yuborishda yordam beraman.",
        reply_markup=main_menu(m.from_user.id)
    )


@dp.message_handler(lambda m: m.text == "➕ Kanal qo'shish", state="*")
async def add_channel(m: types.Message, state: FSMContext):
    await state.finish()
    msg = (
        "📢 Kanal qo‘shish uchun:\n\n"
        "1️⃣ Botni kanalga <b>admin</b> qilib qo‘shing.\n"
        "2️⃣ Kanaldan xabarni menga <b>forward</b> qiling."
    )
    await m.answer(msg)
    await AddChannel.waiting_for_forward.set()


@dp.message_handler(content_types=ContentType.ANY, state=AddChannel.waiting_for_forward)
async def handle_forward(m: types.Message, state: FSMContext):
    if not m.forward_from_chat or m.forward_from_chat.type != "channel":
        await m.answer("❌ Iltimos, <b>kanaldan</b> forward yuboring.")
        return
    ch = m.forward_from_chat
    try:
        me = await bot.get_chat_member(ch.id, bot.id)
        if me.status not in ["administrator", "creator"]:
            await m.answer("⚠️ Bot kanalga admin sifatida qo‘shilmagan.")
            return
    except Exception:
        await m.answer("⚠️ Bot kanalga admin sifatida qo‘shilmagan.")
        return

    if db.add_channel(m.from_user.id, ch.id, ch.title):
        await m.answer(f"✅ <b>{ch.title}</b> qo‘shildi!", reply_markup=main_menu(m.from_user.id))
    else:
        await m.answer(f"ℹ️ <b>{ch.title}</b> allaqachon qo‘shilgan.", reply_markup=main_menu(m.from_user.id))
    await state.finish()


@dp.message_handler(lambda m: m.text == "📢 Reklama yuborish", state="*")
async def send_ad_start(m: types.Message, state: FSMContext):
    uid = m.from_user.id
    user_selections[uid] = set()
    kb = channel_keyboard(uid, user_selections[uid])
    if not kb:
        await m.answer("Sizda hali kanallar yo‘q.", reply_markup=main_menu(uid))
        return
    await m.answer("📋 Reklama yuboriladigan kanallarni tanlang:", reply_markup=kb)
    await SendAd.selecting_channels.set()


@dp.callback_query_handler(channel_cb.filter(action="toggle"), state=SendAd.selecting_channels)
async def toggle_channel(c: types.CallbackQuery, callback_data: dict):
    uid = c.from_user.id
    cid = int(callback_data["cid"])
    if uid not in user_selections:
        user_selections[uid] = set()
    if cid in user_selections[uid]:
        user_selections[uid].remove(cid)
    else:
        user_selections[uid].add(cid)
    await c.message.edit_reply_markup(channel_keyboard(uid, user_selections[uid]))
    await c.answer()


@dp.callback_query_handler(channel_cb.filter(action="confirm"), state=SendAd.selecting_channels)
async def confirm_selection(c: types.CallbackQuery, state: FSMContext):
    uid = c.from_user.id
    selected = list(user_selections.get(uid, []))
    if not selected:
        await c.answer("Kanal tanlanmadi!", show_alert=True)
        return
    await state.update_data(chs=selected)
    await c.message.edit_text("📩 Endi reklamani yuboring (matn, rasm yoki video bo‘lishi mumkin)")
    await SendAd.waiting_for_content.set()


@dp.message_handler(content_types=ContentType.ANY, state=SendAd.waiting_for_content)
async def handle_ad_content(m: types.Message, state: FSMContext):
    data = await state.get_data()
    await state.update_data(msg=(m.chat.id, m.message_id))
    kb = InlineKeyboardMarkup().add(
        InlineKeyboardButton("✅ Yuborish", callback_data="send_confirm"),
        InlineKeyboardButton("❌ Bekor", callback_data="send_cancel")
    )
    await m.answer("Rekama yuborilsinmi?", reply_markup=kb)
    await SendAd.confirm_send.set()


@dp.callback_query_handler(lambda c: c.data == "send_confirm", state=SendAd.confirm_send)
async def send_ad_confirm(c: types.CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("chs", [])
    chat_id, msg_id = data.get("msg")
    ok, fail = 0, 0
    for ch in selected:
        try:
            await bot.copy_message(ch, chat_id, msg_id)
            ok += 1
        except Exception as e:
            fail += 1
            logger.warning(f"Yuborilmadi {ch}: {e}")
        await asyncio.sleep(0.5)
    await c.message.edit_text(f"✅ Yuborildi: {ok}\n❌ Xatolik: {fail}")
    await state.finish()


@dp.callback_query_handler(lambda c: c.data == "send_cancel", state=SendAd.confirm_send)
async def cancel_ad(c: types.CallbackQuery, state: FSMContext):
    await c.message.edit_text("❌ Bekor qilindi.")
    await state.finish()


@dp.message_handler(lambda m: m.text == "📊 Statistika")
async def stats(m: types.Message):
    if m.from_user.id != ADMIN_ID:
        await m.answer("⛔ Faqat admin uchun.")
        return
    s = db.get_stats()
    text = (f"📊 <b>Statistika</b>\n\n"
            f"👥 Foydalanuvchilar: {s['total_users']}\n"
            f"📢 Kanallar: {s['total_channels']}")
    await m.answer(text, parse_mode="HTML")


# ════════════════════════════════════════════════════
# 🧩 STARTUP & RUN FOREVER LOOP (Render uchun)
# ════════════════════════════════════════════════════

async def on_startup():
    logger.info("🚀 Bot ishga tushmoqda...")
    try:
        db.get_stats()
        logger.info("✅ Sheets ulanish muvaffaqiyatli")
    except Exception as e:
        logger.error(f"⚠️ Sheets ulanish xatosi: {e}")

    app = web.Application()
    app.router.add_get("/", lambda req: web.Response(text="🤖 ReklamaBot ishga tushdi!"))
    app.router.add_get("/health", lambda req: web.Response(text="OK"))
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logger.info(f"🌐 Web server: http://0.0.0.0:{PORT}")
    asyncio.create_task(dp.start_polling(skip_updates=True))


async def main():
    await on_startup()
    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logger.info("🛑 Bot to‘xtatildi")
