"""
👑 Admin handlerlar - asosiy menyu va sozlamalar
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command, CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext

from config import config
from database.db import Database
from keyboards.keyboards import (
    main_menu_kb, back_kb, settings_kb, users_list_kb, user_detail_kb
)
from filters.admin_filter import IsAdmin
from utils.helpers import format_datetime

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


# ─── START ────────────────────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(msg: Message, db: Database):
    user = await db.get_user(msg.from_user.id)
    name = msg.from_user.first_name

    await msg.answer(
        f"👋 Salom, <b>{name}</b>!\n\n"
        f"🤖 <b>AdBot Pro</b> - Professional Telegram Reklama Boti\n\n"
        f"📢 Kanallar va guruhlarda avtomatik reklama tarqating\n"
        f"📊 Batafsil statistika kuzating\n"
        f"🕐 Jadvalga muvofiq yuborish imkoniyati\n\n"
        f"Quyidagi menyudan kerakli bo'limni tanlang:",
        reply_markup=main_menu_kb()
    )


@router.message(Command("help"))
async def cmd_help(msg: Message):
    await msg.answer(
        "📖 <b>Buyruqlar ro'yxati:</b>\n\n"
        "🔸 <b>Reklama boshqaruvi:</b>\n"
        "  /ads - Reklamalar ro'yxati\n"
        "  /create_ad - Yangi reklama yaratish\n\n"
        "🔸 <b>Chat boshqaruvi:</b>\n"
        "  /chats - Chatlar ro'yxati\n"
        "  /add_chat - Chat qo'shish\n\n"
        "🔸 <b>Broadcast:</b>\n"
        "  /broadcast - Yuborish boshqaruvi\n"
        "  /scheduler - Jadval boshqaruvi\n\n"
        "🔸 <b>Statistika:</b>\n"
        "  /stats - Umumiy statistika\n\n"
        "🔸 <b>Boshqaruv:</b>\n"
        "  /settings - Sozlamalar\n"
        "  /users - Foydalanuvchilar\n"
        "  /ban <id> - Ban qilish\n"
        "  /unban <id> - Bandan chiqarish\n"
        "  /status - Bot holati\n",
        reply_markup=main_menu_kb()
    )


@router.message(Command("status"))
async def cmd_status(msg: Message, db: Database, scheduler):
    stats = await db.get_global_stats()
    sched_count = len(await db.get_active_broadcasts())

    await msg.answer(
        f"🤖 <b>Bot holati:</b>\n\n"
        f"👥 Foydalanuvchilar: <b>{stats['users']:,}</b>\n"
        f"📡 Aktiv chatlar: <b>{stats['chats']:,}</b>\n"
        f"📢 Reklamalar: <b>{stats['ads']:,}</b>\n"
        f"🕐 Aktiv jadvallar: <b>{sched_count}</b>\n"
        f"✅ Jami yuborilgan: <b>{stats['total_sent']:,}</b>\n"
        f"❌ Xatoliklar: <b>{stats['total_failed']:,}</b>\n"
    )


# ─── MENYU NAVIGATSIYA ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "back_main")
async def cb_back_main(cb: CallbackQuery):
    await cb.message.edit_text(
        "🏠 <b>Asosiy menyu</b>\n\nQuyidagi bo'limdan birini tanlang:",
        reply_markup=main_menu_kb()
    )
    # reply kb qayta ko'rsatish
    await cb.answer()


# ─── SOZLAMALAR ───────────────────────────────────────────────────────────────

@router.message(F.text == "⚙️ Sozlamalar")
@router.message(Command("settings"))
async def menu_settings(msg: Message):
    await msg.answer("⚙️ <b>Sozlamalar</b>", reply_markup=settings_kb())


@router.callback_query(F.data == "setting_about")
async def cb_setting_about(cb: CallbackQuery):
    await cb.message.edit_text(
        "ℹ️ <b>AdBot Pro haqida</b>\n\n"
        "🤖 Versiya: 2.0.0\n"
        "🛠 Python + aiogram 3.x\n"
        "📊 SQLite database\n"
        "⏰ AsyncIO scheduler\n\n"
        "✨ Xususiyatlar:\n"
        "• Inline tugmalar bilan reklama\n"
        "• Rasm, video, hujjat qo'llab-quvvatlash\n"
        "• Avtomatik jadval\n"
        "• Batafsil statistika\n"
        "• Ko'p kanal/guruh boshqaruvi",
        reply_markup=back_kb("back_settings")
    )
    await cb.answer()


@router.callback_query(F.data == "back_settings")
async def cb_back_settings(cb: CallbackQuery):
    await cb.message.edit_text("⚙️ <b>Sozlamalar</b>", reply_markup=settings_kb())
    await cb.answer()


# ─── FOYDALANUVCHILAR ─────────────────────────────────────────────────────────

@router.message(F.text == "👥 Foydalanuvchilar")
@router.message(Command("users"))
async def menu_users(msg: Message, db: Database):
    users = await db.get_all_users()
    if not users:
        await msg.answer("👥 Foydalanuvchilar yo'q", reply_markup=back_kb())
        return
    await msg.answer(
        f"👥 <b>Foydalanuvchilar</b> ({len(users)} ta)",
        reply_markup=users_list_kb(users)
    )


@router.callback_query(F.data.startswith("users_page:"))
async def cb_users_page(cb: CallbackQuery, db: Database):
    page = int(cb.data.split(":")[1])
    users = await db.get_all_users()
    await cb.message.edit_text(
        f"👥 <b>Foydalanuvchilar</b> ({len(users)} ta)",
        reply_markup=users_list_kb(users, page)
    )
    await cb.answer()


@router.callback_query(F.data.startswith("user_view:"))
async def cb_user_view(cb: CallbackQuery, db: Database):
    user_id = int(cb.data.split(":")[1])
    user = await db.get_user(user_id)
    if not user:
        await cb.answer("Foydalanuvchi topilmadi!", show_alert=True)
        return

    name = user.get("full_name") or "Noma'lum"
    username = f"@{user['username']}" if user.get("username") else "Yo'q"
    status = "🚫 Banlangan" if user["is_banned"] else ("👑 Admin" if user["is_admin"] else "👤 Oddiy")

    await cb.message.edit_text(
        f"👤 <b>Foydalanuvchi ma'lumoti</b>\n\n"
        f"🆔 ID: <code>{user_id}</code>\n"
        f"👤 Ism: {name}\n"
        f"📛 Username: {username}\n"
        f"🔖 Status: {status}\n"
        f"📅 Qo'shilgan: {user.get('created_at', 'N/A')}\n"
        f"🕐 So'nggi faollik: {user.get('last_seen', 'N/A')}",
        reply_markup=user_detail_kb(user_id, bool(user["is_banned"]), bool(user["is_admin"]))
    )
    await cb.answer()


@router.callback_query(F.data.startswith("user_ban:"))
async def cb_user_ban(cb: CallbackQuery, db: Database):
    user_id = int(cb.data.split(":")[1])
    await db.ban_user(user_id)
    await cb.answer("✅ Foydalanuvchi banlandi!", show_alert=True)
    user = await db.get_user(user_id)
    await cb.message.edit_reply_markup(
        reply_markup=user_detail_kb(user_id, True, bool(user["is_admin"]))
    )


@router.callback_query(F.data.startswith("user_unban:"))
async def cb_user_unban(cb: CallbackQuery, db: Database):
    user_id = int(cb.data.split(":")[1])
    await db.unban_user(user_id)
    await cb.answer("✅ Foydalanuvchi bandan chiqarildi!", show_alert=True)
    user = await db.get_user(user_id)
    await cb.message.edit_reply_markup(
        reply_markup=user_detail_kb(user_id, False, bool(user["is_admin"]))
    )


@router.callback_query(F.data == "back_users")
async def cb_back_users(cb: CallbackQuery, db: Database):
    users = await db.get_all_users()
    await cb.message.edit_text(
        f"👥 <b>Foydalanuvchilar</b> ({len(users)} ta)",
        reply_markup=users_list_kb(users)
    )
    await cb.answer()


# ─── BAN/UNBAN BUYRUQLARI ─────────────────────────────────────────────────────

@router.message(Command("ban"))
async def cmd_ban(msg: Message, db: Database):
    args = msg.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await msg.answer("❌ Foydalanish: /ban <user_id>")
        return
    user_id = int(args[1])
    await db.ban_user(user_id)
    await msg.answer(f"✅ Foydalanuvchi {user_id} banlandi!")


@router.message(Command("unban"))
async def cmd_unban(msg: Message, db: Database):
    args = msg.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await msg.answer("❌ Foydalanish: /unban <user_id>")
        return
    user_id = int(args[1])
    await db.unban_user(user_id)
    await msg.answer(f"✅ Foydalanuvchi {user_id} bandan chiqarildi!")


@router.callback_query(F.data == "noop")
async def cb_noop(cb: CallbackQuery):
    await cb.answer()
