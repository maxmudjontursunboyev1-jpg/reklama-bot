"""
🕐 Scheduler handlerlar - avtomatik yuborish jadvali
"""

import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from datetime import datetime

from database.db import Database
from keyboards.keyboards import (
    broadcast_list_kb, broadcast_detail_kb, ads_list_kb,
    chat_selector_kb, back_kb, cancel_kb
)
from filters.admin_filter import IsAdmin
from utils.helpers import send_ad_message

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


class ScheduleCreate(StatesGroup):
    select_ad = State()
    select_chats = State()
    interval = State()
    start_time = State()
    end_time = State()
    recurring = State()


# ─── SCHEDULER MENYU ──────────────────────────────────────────────────────────

@router.message(F.text == "🕐 Scheduler")
@router.message(Command("scheduler"))
async def menu_scheduler(msg: Message, db: Database):
    broadcasts = await db.get_all_broadcasts()
    active = sum(1 for b in broadcasts if b["is_active"])
    await msg.answer(
        f"🕐 <b>Scheduler</b>\n\n"
        f"Jami: {len(broadcasts)} ta | Aktiv: {active} ta",
        reply_markup=broadcast_list_kb(broadcasts)
    )


@router.callback_query(F.data == "back_scheduler")
async def cb_back_scheduler(cb: CallbackQuery, db: Database):
    broadcasts = await db.get_all_broadcasts()
    await cb.message.edit_text(
        f"🕐 <b>Scheduler</b> ({len(broadcasts)} ta)",
        reply_markup=broadcast_list_kb(broadcasts)
    )
    await cb.answer()


# ─── YANGI BROADCAST YARATISH ─────────────────────────────────────────────────

@router.callback_query(F.data == "broadcast_create")
async def cb_broadcast_create(cb: CallbackQuery, state: FSMContext, db: Database):
    ads = await db.get_all_ads()
    if not ads:
        await cb.answer("❌ Avval reklama yarating!", show_alert=True)
        return

    await state.set_state(ScheduleCreate.select_ad)
    await cb.message.edit_text(
        "🕐 <b>Yangi jadval</b>\n\n1️⃣ Reklamani tanlang:",
        reply_markup=ads_list_kb(ads)
    )
    await cb.answer()


@router.callback_query(F.data.startswith("ad_schedule:"))
async def cb_ad_schedule(cb: CallbackQuery, state: FSMContext, db: Database):
    ad_id = int(cb.data.split(":")[1])
    chats = await db.get_all_chats(active_only=True)

    if not chats:
        await cb.answer("❌ Aktiv chatlar yo'q!", show_alert=True)
        return

    await state.set_state(ScheduleCreate.select_chats)
    await state.update_data(ad_id=ad_id, selected_chats=[])
    await cb.message.edit_text(
        "2️⃣ Chatlarni tanlang:",
        reply_markup=chat_selector_kb(chats, [], "schedule")
    )
    await cb.answer()


@router.callback_query(F.data.startswith("confirm_chats:schedule"))
async def cb_confirm_schedule_chats(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    selected = data.get("selected_chats", [])

    if not selected:
        await cb.answer("❌ Hech bo'lmasa 1 ta chat tanlang!", show_alert=True)
        return

    await state.set_state(ScheduleCreate.interval)
    await cb.message.answer(
        f"✅ {len(selected)} ta chat tanlandi\n\n"
        "3️⃣ <b>Yuborish intervali</b>ni kiriting (daqiqalarda):\n\n"
        "<i>Misol: 60 (har soatda), 30 (har 30 daqiqada), 1440 (har kunda)</i>\n"
        "Minimal: 5 daqiqa",
        reply_markup=cancel_kb()
    )
    await cb.answer()


@router.message(ScheduleCreate.interval)
async def process_interval(msg: Message, state: FSMContext):
    from aiogram.types import ReplyKeyboardRemove
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("❌ Bekor qilindi", reply_markup=ReplyKeyboardRemove())
        return

    if not msg.text.isdigit() or int(msg.text) < 5:
        await msg.answer("❌ Minimal 5 daqiqa! Raqam kiriting:")
        return

    await state.update_data(interval=int(msg.text))
    await state.set_state(ScheduleCreate.start_time)
    await msg.answer(
        "4️⃣ <b>Boshlash vaqti</b>ni kiriting:\n\n"
        "Format: <code>2024-12-31 14:30</code>\n"
        "yoki <b>hozir</b> yozing (darhol boshlash)",
        reply_markup=cancel_kb()
    )


@router.message(ScheduleCreate.start_time)
async def process_start_time(msg: Message, state: FSMContext):
    from aiogram.types import ReplyKeyboardRemove
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("❌", reply_markup=ReplyKeyboardRemove())
        return

    if msg.text.lower() == "hozir":
        start_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    else:
        try:
            dt = datetime.strptime(msg.text.strip(), "%Y-%m-%d %H:%M")
            start_time = dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            await msg.answer("❌ Format noto'g'ri! Misol: 2024-12-31 14:30")
            return

    await state.update_data(start_time=start_time)
    await state.set_state(ScheduleCreate.end_time)
    await msg.answer(
        "5️⃣ <b>Tugash vaqti</b>ni kiriting:\n\n"
        "Format: <code>2024-12-31 23:59</code>\n"
        "yoki <b>yo'q</b> yozing (cheksiz)",
        reply_markup=cancel_kb()
    )


@router.message(ScheduleCreate.end_time)
async def process_end_time(msg: Message, state: FSMContext):
    from aiogram.types import ReplyKeyboardRemove
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("❌", reply_markup=ReplyKeyboardRemove())
        return

    if msg.text.lower() in ("yo'q", "yoq", "none", "-"):
        end_time = None
    else:
        try:
            dt = datetime.strptime(msg.text.strip(), "%Y-%m-%d %H:%M")
            end_time = dt.strftime("%Y-%m-%d %H:%M")
        except ValueError:
            await msg.answer("❌ Format noto'g'ri! yoki 'yo'q' yozing")
            return

    await state.update_data(end_time=end_time)
    await state.set_state(ScheduleCreate.recurring)

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Ha, takrorlansin", callback_data="recurring_yes")
    builder.button(text="1️⃣ Yo'q, bir marta", callback_data="recurring_no")
    await msg.answer(
        "6️⃣ <b>Takrorlansin?</b>\n\n"
        "🔄 Takrorlanuvchi: Har X daqiqada qayta yuboriladi\n"
        "1️⃣ Bir martalik: Belgilangan vaqtda faqat bir marta",
        reply_markup=builder.as_markup()
    )


@router.callback_query(F.data.in_({"recurring_yes", "recurring_no"}))
async def process_recurring(cb: CallbackQuery, state: FSMContext, db: Database):
    is_recurring = cb.data == "recurring_yes"
    data = await state.get_data()
    await state.clear()

    bid = await db.create_broadcast(
        ad_id=data["ad_id"],
        chat_ids=data["selected_chats"],
        interval_min=data["interval"],
        start_time=data["start_time"],
        end_time=data.get("end_time"),
        is_recurring=is_recurring,
        created_by=cb.from_user.id
    )

    ad = await db.get_ad(data["ad_id"])
    recurring_text = "🔄 Takrorlanuvchi" if is_recurring else "1️⃣ Bir martalik"

    await cb.message.edit_text(
        f"✅ <b>Jadval yaratildi!</b>\n\n"
        f"🆔 ID: {bid}\n"
        f"📢 Reklama: {ad['title']}\n"
        f"📡 Chatlar: {len(data['selected_chats'])} ta\n"
        f"⏱ Interval: {data['interval']} daqiqa\n"
        f"🕐 Boshlanish: {data['start_time']}\n"
        f"🏁 Tugash: {data.get('end_time') or 'Cheksiz'}\n"
        f"🔄 Tur: {recurring_text}",
        reply_markup=broadcast_detail_kb(bid, True)
    )
    await cb.answer("✅ Jadval yaratildi!")


# ─── BROADCAST DETAIL ─────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("broadcast_view:"))
async def cb_broadcast_view(cb: CallbackQuery, db: Database):
    bid = int(cb.data.split(":")[1])
    b = await db.get_broadcast(bid)
    if not b:
        await cb.answer("Jadval topilmadi!", show_alert=True)
        return

    ad = await db.get_ad(b["ad_id"])
    ad_title = ad["title"] if ad else "O'chirilgan"
    status = "✅ Aktiv" if b["is_active"] else "⏸ To'xtatilgan"
    recurring = "🔄 Takrorlanuvchi" if b["is_recurring"] else "1️⃣ Bir martalik"

    await cb.message.edit_text(
        f"📋 <b>Jadval #{bid}</b>\n\n"
        f"📢 Reklama: {ad_title}\n"
        f"📡 Chatlar: {len(b['chat_ids'])} ta\n"
        f"⏱ Interval: {b['interval_min']} daqiqa\n"
        f"🕐 Boshlanish: {b['start_time']}\n"
        f"🏁 Tugash: {b.get('end_time') or 'Cheksiz'}\n"
        f"🔄 Tur: {recurring}\n"
        f"🔖 Status: {status}",
        reply_markup=broadcast_detail_kb(bid, bool(b["is_active"]))
    )
    await cb.answer()


@router.callback_query(F.data.startswith("broadcast_stop:"))
async def cb_broadcast_stop(cb: CallbackQuery, db: Database):
    bid = int(cb.data.split(":")[1])
    await db.toggle_broadcast(bid, False)
    await cb.answer("⏸ Jadval to'xtatildi!")
    await cb.message.edit_reply_markup(reply_markup=broadcast_detail_kb(bid, False))


@router.callback_query(F.data.startswith("broadcast_start:"))
async def cb_broadcast_start(cb: CallbackQuery, db: Database):
    bid = int(cb.data.split(":")[1])
    await db.toggle_broadcast(bid, True)
    await cb.answer("▶️ Jadval ishga tushirildi!")
    await cb.message.edit_reply_markup(reply_markup=broadcast_detail_kb(bid, True))


@router.callback_query(F.data.startswith("broadcast_now:"))
async def cb_broadcast_now(cb: CallbackQuery, db: Database, bot: Bot):
    """Hozir yuborish"""
    bid = int(cb.data.split(":")[1])
    b = await db.get_broadcast(bid)
    if not b:
        await cb.answer("Topilmadi!", show_alert=True)
        return

    ad = await db.get_ad(b["ad_id"])
    if not ad:
        await cb.answer("Reklama topilmadi!", show_alert=True)
        return

    await cb.answer("⏳ Yuborilmoqda...")
    success = failed = 0

    for chat_id in b["chat_ids"]:
        try:
            msg_id = await send_ad_message(bot, chat_id, ad)
            await db.log_send(bid, b["ad_id"], chat_id, msg_id, "sent")
            success += 1
        except Exception as e:
            await db.log_send(bid, b["ad_id"], chat_id, status="failed", error=str(e))
            failed += 1

    await cb.message.answer(
        f"📊 <b>Yuborish yakunlandi!</b>\n✅ {success} | ❌ {failed}"
    )


@router.callback_query(F.data.startswith("broadcast_delete:"))
async def cb_broadcast_delete(cb: CallbackQuery, db: Database):
    bid = int(cb.data.split(":")[1])
    await db.delete_broadcast(bid)
    broadcasts = await db.get_all_broadcasts()
    await cb.message.edit_text(
        f"✅ Jadval o'chirildi!\n\n🕐 Jadvallar ({len(broadcasts)} ta)",
        reply_markup=broadcast_list_kb(broadcasts)
    )
    await cb.answer("✅ O'chirildi!")


@router.callback_query(F.data.startswith("broadcast_stats:"))
async def cb_broadcast_stats(cb: CallbackQuery, db: Database):
    bid = int(cb.data.split(":")[1])
    b = await db.get_broadcast(bid)

    async with db.db.execute(
        "SELECT status, COUNT(*) as cnt FROM send_logs WHERE broadcast_id = ? GROUP BY status",
        (bid,)
    ) as cur:
        rows = await cur.fetchall()
        stats = {r["status"]: r["cnt"] for r in rows}

    sent = stats.get("sent", 0)
    failed = stats.get("failed", 0)
    total = sent + failed

    await cb.message.edit_text(
        f"📊 <b>Jadval #{bid} statistikasi</b>\n\n"
        f"✅ Muvaffaqiyatli: {sent}\n"
        f"❌ Xatoliklar: {failed}\n"
        f"📦 Jami: {total}\n"
        f"📈 Samaradorlik: {sent/total*100:.1f}%" if total > 0 else
        f"📊 <b>Jadval #{bid} statistikasi</b>\n\nHali yuborilmagan",
        reply_markup=back_kb(f"broadcast_view:{bid}")
    )
    await cb.answer()
