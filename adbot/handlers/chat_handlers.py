"""
📡 Chat handlerlar - kanal/guruhlarni boshqarish
"""

import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery, ChatMemberUpdated
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.filters.chat_member_updated import ChatMemberUpdatedFilter, JOIN_TRANSITION

from database.db import Database
from keyboards.keyboards import (
    chats_list_kb, chat_detail_kb, back_kb, cancel_kb, ads_list_kb, chat_selector_kb
)
from filters.admin_filter import IsAdmin

logger = logging.getLogger(__name__)
router = Router()


class ChatAdd(StatesGroup):
    waiting_forward = State()


# ─── BOT KANALGA/GURUHGA QO'SHILGANDA AVTOMATIK ──────────────────────────────

@router.my_chat_member(ChatMemberUpdatedFilter(member_status_changed=JOIN_TRANSITION))
async def bot_added_to_chat(event: ChatMemberUpdated, bot: Bot, db: Database):
    """Bot kanal yoki guruhga qo'shilganda"""
    chat = event.chat
    if chat.type not in ("channel", "group", "supergroup"):
        return

    try:
        member_count = await bot.get_chat_member_count(chat.id)
    except:
        member_count = 0

    await db.add_chat(
        chat_id=chat.id,
        title=chat.title or "Nomsiz",
        username=chat.username,
        chat_type=chat.type,
        member_count=member_count,
        added_by=event.from_user.id if event.from_user else 0
    )
    logger.info(f"✅ Bot qo'shildi: {chat.title} ({chat.id})")

    # Adminlarga xabar
    from config import config
    for admin_id in config.ADMIN_IDS:
        try:
            icon = "📢" if chat.type == "channel" else "👥"
            username_str = f"@{chat.username}" if chat.username else "Username yo'q"
            await bot.send_message(
                admin_id,
                f"{icon} <b>Bot yangi chatga qo'shildi!</b>\n\n"
                f"📌 Nom: {chat.title}\n"
                f"🔗 {username_str}\n"
                f"🆔 ID: <code>{chat.id}</code>\n"
                f"👥 A'zolar: {member_count:,}\n"
                f"🔧 Tur: {chat.type}"
            )
        except Exception as e:
            logger.warning(f"Admin {admin_id} ga xabar yuborib bo'lmadi: {e}")


@router.my_chat_member()
async def bot_removed_from_chat(event: ChatMemberUpdated, db: Database):
    """Bot chiqarib yuborilganda"""
    from aiogram.filters.chat_member_updated import LEAVE_TRANSITION
    new_status = event.new_chat_member.status
    if new_status in ("left", "kicked", "banned"):
        await db.remove_chat(event.chat.id)
        logger.info(f"Bot chiqarib yuborildi: {event.chat.title} ({event.chat.id})")


# ─── CHATLAR MENYU ────────────────────────────────────────────────────────────

@router.message(F.text == "📡 Chatlar", IsAdmin())
@router.message(Command("chats"), IsAdmin())
async def menu_chats(msg: Message, db: Database):
    chats = await db.get_all_chats(active_only=False)
    active = sum(1 for c in chats if c["is_active"])
    await msg.answer(
        f"📡 <b>Chatlar ro'yxati</b>\n\n"
        f"Jami: {len(chats)} ta | Aktiv: {active} ta",
        reply_markup=chats_list_kb(chats)
    )


@router.callback_query(F.data == "back_chats", IsAdmin())
async def cb_back_chats(cb: CallbackQuery, db: Database):
    chats = await db.get_all_chats(active_only=False)
    await cb.message.edit_text(
        f"📡 <b>Chatlar ro'yxati</b> ({len(chats)} ta)",
        reply_markup=chats_list_kb(chats)
    )
    await cb.answer()


@router.callback_query(F.data.startswith("chats_page:"), IsAdmin())
async def cb_chats_page(cb: CallbackQuery, db: Database):
    page = int(cb.data.split(":")[1])
    chats = await db.get_all_chats(active_only=False)
    await cb.message.edit_reply_markup(reply_markup=chats_list_kb(chats, page))
    await cb.answer()


@router.callback_query(F.data == "chats_refresh", IsAdmin())
async def cb_chats_refresh(cb: CallbackQuery, db: Database, bot: Bot):
    """Barcha chatlarni yangilash"""
    chats = await db.get_all_chats(active_only=True)
    updated = 0
    for chat in chats:
        try:
            count = await bot.get_chat_member_count(chat["chat_id"])
            await db.update_chat_members(chat["chat_id"], count)
            updated += 1
        except Exception as e:
            logger.warning(f"Chat {chat['chat_id']} yangilashda xato: {e}")

    chats = await db.get_all_chats(active_only=False)
    await cb.message.edit_text(
        f"🔄 <b>Yangilandi!</b> ({updated} ta)\n\n📡 Chatlar: {len(chats)} ta",
        reply_markup=chats_list_kb(chats)
    )
    await cb.answer(f"✅ {updated} ta chat yangilandi")


# ─── CHAT QO'SHISH ────────────────────────────────────────────────────────────

@router.callback_query(F.data == "chat_add", IsAdmin())
@router.message(Command("add_chat"), IsAdmin())
async def start_add_chat(event, state: FSMContext):
    msg = event if isinstance(event, Message) else event.message
    await state.set_state(ChatAdd.waiting_forward)

    text = (
        "📡 <b>Chat qo'shish</b>\n\n"
        "Quyidagilardan birini bajaring:\n\n"
        "1️⃣ Kanaldan/guruhdan <b>istalgan xabarni forward</b> qiling\n\n"
        "2️⃣ Yoki kanal/guruh <b>ID</b> raqamini kiriting:\n"
        "<code>-1001234567890</code>\n\n"
        "💡 Avval botni kanalga/guruhga admin qiling!"
    )
    await msg.answer(text, reply_markup=cancel_kb())
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.message(ChatAdd.waiting_forward, IsAdmin())
async def process_add_chat(msg: Message, state: FSMContext, db: Database, bot: Bot):
    from aiogram.types import ReplyKeyboardRemove

    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("❌ Bekor qilindi", reply_markup=ReplyKeyboardRemove())
        return

    chat_id = None

    # Forward dan chat ID olish
    if msg.forward_from_chat:
        chat_id = msg.forward_from_chat.id
    elif msg.text and msg.text.lstrip("-").isdigit():
        chat_id = int(msg.text.strip())
    else:
        await msg.answer("❓ Forward qiling yoki chat ID raqamini kiriting!")
        return

    try:
        chat_info = await bot.get_chat(chat_id)
        member_count = await bot.get_chat_member_count(chat_id)

        # Bot admin ekanini tekshirish
        bot_member = await bot.get_chat_member(chat_id, (await bot.get_me()).id)
        if bot_member.status not in ("administrator", "creator"):
            await msg.answer(
                "❌ Bot bu chatda admin emas!\n\n"
                "Bot ni admin qilib, qayta urinib ko'ring.",
                reply_markup=ReplyKeyboardRemove()
            )
            await state.clear()
            return

        await db.add_chat(
            chat_id=chat_id,
            title=chat_info.title or "Nomsiz",
            username=chat_info.username,
            chat_type=chat_info.type,
            member_count=member_count,
            added_by=msg.from_user.id
        )

        icon = "📢" if chat_info.type == "channel" else "👥"
        username_str = f"@{chat_info.username}" if chat_info.username else "Username yo'q"

        await state.clear()
        await msg.answer(
            f"✅ <b>Chat qo'shildi!</b>\n\n"
            f"{icon} {chat_info.title}\n"
            f"🔗 {username_str}\n"
            f"🆔 <code>{chat_id}</code>\n"
            f"👥 A'zolar: {member_count:,}",
            reply_markup=ReplyKeyboardRemove()
        )

    except Exception as e:
        await msg.answer(
            f"❌ Xato yuz berdi:\n<code>{str(e)}</code>\n\n"
            f"Bot kanal/guruhda admin ekanini tekshiring!",
            reply_markup=ReplyKeyboardRemove()
        )
        await state.clear()


# ─── CHAT DETAIL ──────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("chat_view:"), IsAdmin())
async def cb_chat_view(cb: CallbackQuery, db: Database, bot: Bot):
    chat_id = int(cb.data.split(":")[1])
    chat = await db.get_chat(chat_id)
    if not chat:
        await cb.answer("Chat topilmadi!", show_alert=True)
        return

    icon = "📢" if chat["chat_type"] == "channel" else "👥"
    username_str = f"@{chat['username']}" if chat.get("username") else "Yo'q"
    status = "✅ Aktiv" if chat["is_active"] else "❌ Nofaol"

    await cb.message.edit_text(
        f"{icon} <b>{chat['title']}</b>\n\n"
        f"🆔 ID: <code>{chat_id}</code>\n"
        f"🔗 Username: {username_str}\n"
        f"📋 Tur: {chat['chat_type']}\n"
        f"👥 A'zolar: {chat['member_count']:,}\n"
        f"🔖 Status: {status}\n"
        f"📅 Qo'shilgan: {chat['added_at']}\n"
        f"🕐 So'nggi tekshiruv: {chat['last_checked']}",
        reply_markup=chat_detail_kb(chat_id, bool(chat["is_active"]))
    )
    await cb.answer()


@router.callback_query(F.data.startswith("chat_refresh:"), IsAdmin())
async def cb_chat_refresh(cb: CallbackQuery, db: Database, bot: Bot):
    chat_id = int(cb.data.split(":")[1])
    try:
        chat_info = await bot.get_chat(chat_id)
        count = await bot.get_chat_member_count(chat_id)
        await db.update_chat_members(chat_id, count)
        await db.add_chat(
            chat_id=chat_id,
            title=chat_info.title or "Nomsiz",
            username=chat_info.username,
            chat_type=chat_info.type,
            member_count=count,
            added_by=0
        )
        await cb.answer(f"✅ Yangilandi! A'zolar: {count:,}")
        chat = await db.get_chat(chat_id)
        await cb.message.edit_reply_markup(
            reply_markup=chat_detail_kb(chat_id, bool(chat["is_active"]))
        )
    except Exception as e:
        await cb.answer(f"❌ Xato: {str(e)[:100]}", show_alert=True)


@router.callback_query(F.data.startswith("chat_deactivate:"), IsAdmin())
async def cb_chat_deactivate(cb: CallbackQuery, db: Database):
    chat_id = int(cb.data.split(":")[1])
    await db.remove_chat(chat_id)
    await cb.answer("⏸ Chat nofaol qilindi")
    await cb.message.edit_reply_markup(reply_markup=chat_detail_kb(chat_id, False))


@router.callback_query(F.data.startswith("chat_activate:"), IsAdmin())
async def cb_chat_activate(cb: CallbackQuery, db: Database):
    chat_id = int(cb.data.split(":")[1])
    await db.db.execute("UPDATE chats SET is_active = 1 WHERE chat_id = ?", (chat_id,))
    await db.db.commit()
    await cb.answer("✅ Chat faollashtirildi")
    await cb.message.edit_reply_markup(reply_markup=chat_detail_kb(chat_id, True))


@router.callback_query(F.data.startswith("chat_delete:"), IsAdmin())
async def cb_chat_delete(cb: CallbackQuery, db: Database):
    chat_id = int(cb.data.split(":")[1])
    await db.db.execute("DELETE FROM chats WHERE chat_id = ?", (chat_id,))
    await db.db.commit()
    chats = await db.get_all_chats(active_only=False)
    await cb.message.edit_text(
        f"✅ Chat o'chirildi!\n\n📡 Chatlar ({len(chats)} ta)",
        reply_markup=chats_list_kb(chats)
    )
    await cb.answer("✅ O'chirildi!")


@router.callback_query(F.data == "chats_clear", IsAdmin())
async def cb_chats_clear(cb: CallbackQuery, db: Database):
    from keyboards.keyboards import InlineKeyboardMarkup, InlineKeyboardButton
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Ha, barchasini o'chir", callback_data="confirm_clear_chats")
    builder.button(text="❌ Bekor qilish", callback_data="back_chats")
    await cb.message.edit_text(
        "⚠️ Barcha chatlarni o'chirishni tasdiqlaysizmi?",
        reply_markup=builder.as_markup()
    )
    await cb.answer()


@router.callback_query(F.data == "confirm_clear_chats", IsAdmin())
async def cb_confirm_clear_chats(cb: CallbackQuery, db: Database):
    await db.db.execute("DELETE FROM chats")
    await db.db.commit()
    await cb.message.edit_text(
        "✅ Barcha chatlar o'chirildi!",
        reply_markup=back_kb("back_chats")
    )
    await cb.answer()


@router.callback_query(F.data.startswith("chat_send_ad:"), IsAdmin())
async def cb_chat_send_ad(cb: CallbackQuery, db: Database, state: FSMContext):
    """Bitta chatga reklama yuborish"""
    chat_id = int(cb.data.split(":")[1])
    ads = await db.get_all_ads()
    if not ads:
        await cb.answer("❌ Reklama yo'q!", show_alert=True)
        return
    await state.update_data(target_chat_id=chat_id)
    await cb.message.edit_text(
        "📢 Qaysi reklamani yuborish?",
        reply_markup=ads_list_kb(ads)
    )
    await cb.answer()
