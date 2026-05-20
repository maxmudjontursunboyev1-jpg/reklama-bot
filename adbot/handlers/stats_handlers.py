"""
📊 Statistika handlerlar
"""

import logging
from aiogram import Router, F
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery

from database.db import Database
from keyboards.keyboards import stats_kb, back_kb
from filters.admin_filter import IsAdmin

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


@router.message(F.text == "📊 Statistika")
@router.message(Command("stats"))
async def menu_stats(msg: Message, db: Database):
    await msg.answer("📊 <b>Statistika bo'limi</b>", reply_markup=stats_kb())


@router.callback_query(F.data == "stats_global")
async def cb_stats_global(cb: CallbackQuery, db: Database):
    stats = await db.get_global_stats()
    rate = ""
    total = stats["total_sent"] + stats["total_failed"]
    if total > 0:
        rate = f"\n📈 Muvaffaqiyat: {stats['total_sent']/total*100:.1f}%"

    await cb.message.edit_text(
        f"📊 <b>Umumiy statistika</b>\n\n"
        f"👥 Foydalanuvchilar: {stats['users']:,}\n"
        f"📡 Aktiv chatlar: {stats['chats']:,}\n"
        f"📢 Reklamalar: {stats['ads']:,}\n"
        f"🕐 Aktiv jadvallar: {stats['active_broadcasts']:,}\n\n"
        f"📤 Jami yuborilgan: {stats['total_sent']:,}\n"
        f"❌ Xatoliklar: {stats['total_failed']:,}"
        f"{rate}",
        reply_markup=back_kb("back_stats")
    )
    await cb.answer()


@router.callback_query(F.data == "stats_by_ads")
async def cb_stats_by_ads(cb: CallbackQuery, db: Database):
    ads = await db.get_all_ads()
    if not ads:
        await cb.answer("Reklama yo'q!", show_alert=True)
        return

    text = "📢 <b>Reklamalar bo'yicha statistika</b>\n\n"
    for ad in ads[:20]:
        s = await db.get_send_stats(ad["id"])
        sent = s.get("sent", 0)
        failed = s.get("failed", 0)
        text += f"• {ad['title'][:25]}: ✅{sent} ❌{failed}\n"

    await cb.message.edit_text(text, reply_markup=back_kb("back_stats"))
    await cb.answer()


@router.callback_query(F.data == "stats_logs")
async def cb_stats_logs(cb: CallbackQuery, db: Database):
    logs = await db.get_recent_logs(20)
    if not logs:
        await cb.answer("Loglar yo'q!", show_alert=True)
        return

    text = "📝 <b>So'nggi 20 ta log</b>\n\n"
    for log in logs:
        icon = "✅" if log["status"] == "sent" else "❌"
        chat = log.get("chat_title") or str(log["chat_id"])
        text += f"{icon} {chat[:20]} | {log['sent_at'][:16]}\n"

    await cb.message.edit_text(text, reply_markup=back_kb("back_stats"))
    await cb.answer()


@router.callback_query(F.data == "back_stats")
async def cb_back_stats(cb: CallbackQuery):
    await cb.message.edit_text("📊 <b>Statistika bo'limi</b>", reply_markup=stats_kb())
    await cb.answer()
