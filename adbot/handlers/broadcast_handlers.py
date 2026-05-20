"""
📤 Broadcast handlerlar - reklama yuborish
"""

import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import Database
from keyboards.keyboards import (
    chat_selector_kb, ads_list_kb, back_kb, send_confirm_kb, ad_preview_buttons
)
from filters.admin_filter import IsAdmin
from utils.helpers import send_ad_message

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


class BroadcastNow(StatesGroup):
    select_ad = State()
    select_chats = State()
    confirm = State()


# ─── AD_SEND ──────────────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ad_send:"))
async def cb_ad_send(cb: CallbackQuery, db: Database, state: FSMContext):
    ad_id = int(cb.data.split(":")[1])
    chats = await db.get_all_chats(active_only=True)

    if not chats:
        await cb.answer("❌ Aktiv chatlar yo'q! Avval chat qo'shing.", show_alert=True)
        return

    await state.set_state(BroadcastNow.select_chats)
    await state.update_data(ad_id=ad_id, selected_chats=[])

    await cb.message.edit_text(
        f"📤 <b>Reklama yuborish</b>\n\n"
        f"Chat(lar)ni tanlang ({len(chats)} ta mavjud):",
        reply_markup=chat_selector_kb(chats, [], "send")
    )
    await cb.answer()


@router.callback_query(F.data.startswith("select_chat:"))
async def cb_select_chat(cb: CallbackQuery, state: FSMContext, db: Database):
    parts = cb.data.split(":")
    chat_id = int(parts[1])
    action = parts[2]

    data = await state.get_data()
    selected = data.get("selected_chats", [])

    if chat_id in selected:
        selected.remove(chat_id)
    else:
        selected.append(chat_id)

    await state.update_data(selected_chats=selected)
    chats = await db.get_all_chats(active_only=True)
    await cb.message.edit_reply_markup(
        reply_markup=chat_selector_kb(chats, selected, action)
    )
    await cb.answer(f"✅ {len(selected)} ta tanlandi")


@router.callback_query(F.data.startswith("select_all_chats:"))
async def cb_select_all(cb: CallbackQuery, state: FSMContext, db: Database):
    action = cb.data.split(":")[1]
    chats = await db.get_all_chats(active_only=True)
    selected = [c["chat_id"] for c in chats]
    await state.update_data(selected_chats=selected)
    await cb.message.edit_reply_markup(
        reply_markup=chat_selector_kb(chats, selected, action)
    )
    await cb.answer(f"✅ Barcha {len(selected)} ta tanlandi")


@router.callback_query(F.data.startswith("deselect_all_chats:"))
async def cb_deselect_all(cb: CallbackQuery, state: FSMContext, db: Database):
    action = cb.data.split(":")[1]
    await state.update_data(selected_chats=[])
    chats = await db.get_all_chats(active_only=True)
    await cb.message.edit_reply_markup(
        reply_markup=chat_selector_kb(chats, [], action)
    )
    await cb.answer("❌ Tanlash bekor qilindi")


@router.callback_query(F.data.startswith("confirm_chats:send"))
async def cb_confirm_send(cb: CallbackQuery, state: FSMContext, db: Database):
    data = await state.get_data()
    selected = data.get("selected_chats", [])
    ad_id = data.get("ad_id")

    if not selected:
        await cb.answer("❌ Hech bo'lmasa 1 ta chat tanlang!", show_alert=True)
        return

    ad = await db.get_ad(ad_id)
    await cb.message.edit_text(
        f"📤 <b>Tasdiqlash</b>\n\n"
        f"📢 Reklama: <b>{ad['title']}</b>\n"
        f"📡 Chatlar soni: <b>{len(selected)} ta</b>\n\n"
        f"Yuborishni tasdiqlaysizmi?",
        reply_markup=send_confirm_kb(ad_id, ",".join(map(str, selected)))
    )
    await cb.answer()


@router.callback_query(F.data.startswith("confirm_send:"))
async def cb_do_send(cb: CallbackQuery, state: FSMContext, db: Database, bot: Bot):
    parts = cb.data.split(":")
    ad_id = int(parts[1])
    chat_ids = [int(x) for x in parts[2].split(",") if x]

    await state.clear()
    ad = await db.get_ad(ad_id)

    progress_msg = await cb.message.edit_text(
        f"⏳ <b>Yuborilmoqda...</b>\n\n"
        f"0/{len(chat_ids)} ta chat"
    )

    success = 0
    failed = 0
    failed_chats = []

    for i, chat_id in enumerate(chat_ids):
        try:
            msg_id = await send_ad_message(bot, chat_id, ad)
            await db.log_send(None, ad_id, chat_id, msg_id, "sent")
            success += 1
        except Exception as e:
            await db.log_send(None, ad_id, chat_id, status="failed", error=str(e))
            failed += 1
            chat = await db.get_chat(chat_id)
            failed_chats.append(chat["title"] if chat else str(chat_id))
            logger.error(f"Chat {chat_id} ga yuborishda xato: {e}")

        # Progress yangilash
        if (i + 1) % 5 == 0 or (i + 1) == len(chat_ids):
            try:
                await progress_msg.edit_text(
                    f"⏳ <b>Yuborilmoqda...</b>\n\n"
                    f"{i+1}/{len(chat_ids)} ta chat\n"
                    f"✅ {success} | ❌ {failed}"
                )
            except:
                pass

    # Yakuniy natija
    result_text = (
        f"📊 <b>Yuborish yakunlandi!</b>\n\n"
        f"✅ Muvaffaqiyatli: {success}\n"
        f"❌ Xatolik: {failed}\n"
        f"📦 Jami: {len(chat_ids)}"
    )
    if failed_chats:
        result_text += f"\n\n❌ Xatoliklar:\n" + "\n".join(f"• {t}" for t in failed_chats[:10])

    await progress_msg.edit_text(result_text, reply_markup=back_kb("back_ads"))
    await cb.answer()
