"""
📢 Reklama handlerlar - yaratish, tahrirlash, o'chirish
"""

import logging
from aiogram import Router, F, Bot
from aiogram.filters import Command
from aiogram.types import Message, CallbackQuery
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

from database.db import Database
from keyboards.keyboards import (
    ads_list_kb, ad_detail_kb, ad_edit_kb, back_kb,
    buttons_manager_kb, ad_preview_buttons, cancel_kb, skip_cancel_kb
)
from filters.admin_filter import IsAdmin
from utils.helpers import send_ad_message

logger = logging.getLogger(__name__)
router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())


class AdCreate(StatesGroup):
    title = State()
    text = State()
    media = State()
    buttons = State()


class AdEdit(StatesGroup):
    title = State()
    text = State()
    media = State()


class ButtonAdd(StatesGroup):
    text = State()
    url = State()


# ─── REKLAMALAR RO'YXATI ──────────────────────────────────────────────────────

@router.message(F.text == "📢 Reklamalar")
@router.message(Command("ads"))
async def menu_ads(msg: Message, db: Database):
    ads = await db.get_all_ads()
    text = f"📢 <b>Reklamalar</b> ({len(ads)} ta)\n\n"
    if not ads:
        text += "Hozircha reklama yo'q. Yangi reklama yarating!"
    await msg.answer(text, reply_markup=ads_list_kb(ads))


@router.callback_query(F.data == "back_ads")
async def cb_back_ads(cb: CallbackQuery, db: Database):
    ads = await db.get_all_ads()
    await cb.message.edit_text(
        f"📢 <b>Reklamalar</b> ({len(ads)} ta)",
        reply_markup=ads_list_kb(ads)
    )
    await cb.answer()


# ─── REKLAMA KO'RISH ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ad_view:"))
async def cb_ad_view(cb: CallbackQuery, db: Database):
    ad_id = int(cb.data.split(":")[1])
    ad = await db.get_ad(ad_id)
    if not ad:
        await cb.answer("Reklama topilmadi!", show_alert=True)
        return

    media_info = f"\n🖼 Media: {ad['media_type']}" if ad.get("media_type") else ""
    btn_count = len(ad.get("buttons", []))
    status_map = {"draft": "📝 Qoralama", "active": "✅ Aktiv", "paused": "⏸ To'xtatilgan"}

    text = (
        f"📢 <b>{ad['title']}</b>\n\n"
        f"📝 Matn:\n{ad['text'][:300]}{'...' if len(ad['text']) > 300 else ''}\n"
        f"{media_info}\n"
        f"🔘 Inline tugmalar: {btn_count} ta\n"
        f"📌 Status: {status_map.get(ad['status'], ad['status'])}\n"
        f"📅 Yaratilgan: {ad['created_at']}"
    )
    await cb.message.edit_text(text, reply_markup=ad_detail_kb(ad_id, ad["status"]))
    await cb.answer()


# ─── REKLAMA YARATISH ─────────────────────────────────────────────────────────

@router.callback_query(F.data == "ad_create")
@router.message(Command("create_ad"))
async def start_create_ad(event, state: FSMContext):
    msg = event if isinstance(event, Message) else event.message
    await state.set_state(AdCreate.title)
    await msg.answer(
        "📢 <b>Yangi reklama yaratish</b>\n\n"
        "1️⃣ Reklama <b>sarlavhasini</b> kiriting:\n"
        "<i>(Bu faqat sizga ko'rinadi, reklama ichida bo'lmaydi)</i>",
        reply_markup=cancel_kb()
    )
    if isinstance(event, CallbackQuery):
        await event.answer()


@router.message(AdCreate.title)
async def process_ad_title(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("❌ Bekor qilindi", reply_markup=__import__('aiogram.types', fromlist=['ReplyKeyboardRemove']).ReplyKeyboardRemove())
        return

    await state.update_data(title=msg.text[:100])
    await state.set_state(AdCreate.text)
    await msg.answer(
        "2️⃣ Reklama <b>matnini</b> kiriting:\n\n"
        "💡 HTML formatlash qo'llab-quvvatlanadi:\n"
        "<code>&lt;b&gt;qalin&lt;/b&gt;</code>, <code>&lt;i&gt;kursiv&lt;/i&gt;</code>, "
        "<code>&lt;a href='url'&gt;havola&lt;/a&gt;</code>",
        reply_markup=cancel_kb()
    )


@router.message(AdCreate.text)
async def process_ad_text(msg: Message, state: FSMContext):
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        from aiogram.types import ReplyKeyboardRemove
        await msg.answer("❌ Bekor qilindi", reply_markup=ReplyKeyboardRemove())
        return

    await state.update_data(text=msg.text[:4096])
    await state.set_state(AdCreate.media)
    await msg.answer(
        "3️⃣ <b>Media</b> qo'shing (ixtiyoriy):\n\n"
        "📷 Rasm, 🎥 Video, 📄 Hujjat yuboring\n"
        "yoki <b>O'tkazib yuborish</b> tugmasini bosing",
        reply_markup=skip_cancel_kb()
    )


@router.message(AdCreate.media)
async def process_ad_media(msg: Message, state: FSMContext, db: Database):
    from aiogram.types import ReplyKeyboardRemove

    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("❌ Bekor qilindi", reply_markup=ReplyKeyboardRemove())
        return

    media_type = None
    media_id = None

    if msg.text == "⏭ O'tkazib yuborish":
        pass
    elif msg.photo:
        media_type = "photo"
        media_id = msg.photo[-1].file_id
    elif msg.video:
        media_type = "video"
        media_id = msg.video.file_id
    elif msg.document:
        media_type = "document"
        media_id = msg.document.file_id
    elif msg.animation:
        media_type = "animation"
        media_id = msg.animation.file_id
    else:
        await msg.answer("❓ Rasm, video yoki hujjat yuboring, yoki o'tkazib yuboring")
        return

    data = await state.get_data()
    ad_id = await db.create_ad(
        title=data["title"],
        text=data["text"],
        created_by=msg.from_user.id,
        media_type=media_type,
        media_id=media_id,
    )
    await state.clear()

    await msg.answer(
        f"✅ <b>Reklama yaratildi!</b>\n\n"
        f"🆔 ID: {ad_id}\n"
        f"📌 Sarlavha: {data['title']}\n"
        f"🖼 Media: {media_type or 'Yo\'q'}\n\n"
        f"Endi inline tugmalar qo'shishingiz yoki to'g'ridan-to'g'ri yuborishingiz mumkin!",
        reply_markup=ad_detail_kb(ad_id, "draft")
    )


# ─── REKLAMA TAHRIRLASH ───────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ad_edit:"))
async def cb_ad_edit(cb: CallbackQuery, db: Database):
    ad_id = int(cb.data.split(":")[1])
    ad = await db.get_ad(ad_id)
    if not ad:
        await cb.answer("Reklama topilmadi!", show_alert=True)
        return
    await cb.message.edit_text(
        f"✏️ <b>Reklamani tahrirlash</b>\n\n"
        f"📌 Sarlavha: {ad['title']}\n"
        f"Nima o'zgartirmoqchisiz?",
        reply_markup=ad_edit_kb(ad_id)
    )
    await cb.answer()


@router.callback_query(F.data.startswith("edit_title:"))
async def cb_edit_title(cb: CallbackQuery, state: FSMContext):
    ad_id = int(cb.data.split(":")[1])
    await state.set_state(AdEdit.title)
    await state.update_data(ad_id=ad_id)
    await cb.message.answer("✏️ Yangi sarlavhani kiriting:", reply_markup=cancel_kb())
    await cb.answer()


@router.message(AdEdit.title)
async def process_edit_title(msg: Message, state: FSMContext, db: Database):
    from aiogram.types import ReplyKeyboardRemove
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("❌ Bekor qilindi", reply_markup=ReplyKeyboardRemove())
        return
    data = await state.get_data()
    await db.update_ad(data["ad_id"], title=msg.text[:100])
    await state.clear()
    await msg.answer("✅ Sarlavha yangilandi!", reply_markup=ReplyKeyboardRemove())
    ad = await db.get_ad(data["ad_id"])
    await msg.answer(
        f"📢 <b>{ad['title']}</b>",
        reply_markup=ad_detail_kb(data["ad_id"], ad["status"])
    )


@router.callback_query(F.data.startswith("edit_text:"))
async def cb_edit_text(cb: CallbackQuery, state: FSMContext):
    ad_id = int(cb.data.split(":")[1])
    await state.set_state(AdEdit.text)
    await state.update_data(ad_id=ad_id)
    await cb.message.answer("✏️ Yangi matnni kiriting:", reply_markup=cancel_kb())
    await cb.answer()


@router.message(AdEdit.text)
async def process_edit_text(msg: Message, state: FSMContext, db: Database):
    from aiogram.types import ReplyKeyboardRemove
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("❌", reply_markup=ReplyKeyboardRemove())
        return
    data = await state.get_data()
    await db.update_ad(data["ad_id"], text=msg.text[:4096])
    await state.clear()
    await msg.answer("✅ Matn yangilandi!", reply_markup=ReplyKeyboardRemove())


# ─── STATUS O'ZGARTIRISH ──────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ad_activate:"))
async def cb_ad_activate(cb: CallbackQuery, db: Database):
    ad_id = int(cb.data.split(":")[1])
    await db.update_ad(ad_id, status="active")
    await cb.answer("✅ Reklama faollashtirildi!", show_alert=True)
    await cb.message.edit_reply_markup(reply_markup=ad_detail_kb(ad_id, "active"))


@router.callback_query(F.data.startswith("ad_pause:"))
async def cb_ad_pause(cb: CallbackQuery, db: Database):
    ad_id = int(cb.data.split(":")[1])
    await db.update_ad(ad_id, status="paused")
    await cb.answer("⏸ Reklama to'xtatildi!", show_alert=True)
    await cb.message.edit_reply_markup(reply_markup=ad_detail_kb(ad_id, "paused"))


@router.callback_query(F.data.startswith("ad_delete:"))
async def cb_ad_delete_confirm(cb: CallbackQuery):
    ad_id = int(cb.data.split(":")[1])
    from keyboards.keyboards import confirm_delete_kb
    await cb.message.edit_text(
        "🗑 Reklamani o'chirishni tasdiqlaysizmi?\nBu amalni qaytarib bo'lmaydi!",
        reply_markup=confirm_delete_kb("ad", ad_id)
    )
    await cb.answer()


@router.callback_query(F.data.startswith("confirm_delete:ad:"))
async def cb_confirm_delete_ad(cb: CallbackQuery, db: Database):
    ad_id = int(cb.data.split(":")[2])
    await db.delete_ad(ad_id)
    ads = await db.get_all_ads()
    await cb.message.edit_text(
        f"✅ Reklama o'chirildi!\n\n📢 <b>Reklamalar</b> ({len(ads)} ta)",
        reply_markup=ads_list_kb(ads)
    )
    await cb.answer("✅ O'chirildi!")


# ─── INLINE TUGMALAR ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ad_buttons:"))
async def cb_ad_buttons(cb: CallbackQuery, db: Database):
    ad_id = int(cb.data.split(":")[1])
    ad = await db.get_ad(ad_id)
    if not ad:
        await cb.answer("Reklama topilmadi!", show_alert=True)
        return

    buttons = ad.get("buttons", [])
    text = f"🔘 <b>Inline tugmalar</b> ({len(buttons)} ta)\n\n"
    if buttons:
        for i, btn in enumerate(buttons, 1):
            text += f"{i}. {btn['text']} → {btn['url']}\n"
    else:
        text += "Hali tugma qo'shilmagan"

    await cb.message.edit_text(text, reply_markup=buttons_manager_kb(ad_id, buttons))
    await cb.answer()


@router.callback_query(F.data.startswith("btn_add:"))
async def cb_btn_add(cb: CallbackQuery, state: FSMContext):
    ad_id = int(cb.data.split(":")[1])
    await state.set_state(ButtonAdd.text)
    await state.update_data(ad_id=ad_id)
    await cb.message.answer(
        "🔘 <b>Yangi tugma qo'shish</b>\n\n"
        "1️⃣ Tugma <b>matnini</b> kiriting:",
        reply_markup=cancel_kb()
    )
    await cb.answer()


@router.message(ButtonAdd.text)
async def process_btn_text(msg: Message, state: FSMContext):
    from aiogram.types import ReplyKeyboardRemove
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("❌", reply_markup=ReplyKeyboardRemove())
        return
    await state.update_data(btn_text=msg.text[:64])
    await state.set_state(ButtonAdd.url)
    await msg.answer("2️⃣ Tugma <b>URL</b> manzilini kiriting:\n<i>Misol: https://t.me/channel</i>")


@router.message(ButtonAdd.url)
async def process_btn_url(msg: Message, state: FSMContext, db: Database):
    from aiogram.types import ReplyKeyboardRemove
    if msg.text == "❌ Bekor qilish":
        await state.clear()
        await msg.answer("❌", reply_markup=ReplyKeyboardRemove())
        return

    url = msg.text.strip()
    if not url.startswith(("http://", "https://", "tg://")):
        await msg.answer("❌ URL http:// yoki https:// bilan boshlanishi kerak!")
        return

    data = await state.get_data()
    ad = await db.get_ad(data["ad_id"])
    buttons = ad.get("buttons", [])

    if len(buttons) >= 10:
        await msg.answer("❌ Maksimal 10 ta tugma qo'shish mumkin!")
        await state.clear()
        return

    buttons.append({"text": data["btn_text"], "url": url})
    await db.update_ad(data["ad_id"], buttons=buttons)
    await state.clear()

    await msg.answer(
        f"✅ Tugma qo'shildi!\n🔘 {data['btn_text']} → {url}",
        reply_markup=ReplyKeyboardRemove()
    )
    ad = await db.get_ad(data["ad_id"])
    await msg.answer(
        f"🔘 Tugmalar ({len(ad['buttons'])} ta):",
        reply_markup=buttons_manager_kb(data["ad_id"], ad["buttons"])
    )


@router.callback_query(F.data.startswith("btn_delete:"))
async def cb_btn_delete(cb: CallbackQuery, db: Database):
    parts = cb.data.split(":")
    ad_id = int(parts[1])
    btn_idx = int(parts[2])

    ad = await db.get_ad(ad_id)
    buttons = ad.get("buttons", [])
    if 0 <= btn_idx < len(buttons):
        removed = buttons.pop(btn_idx)
        await db.update_ad(ad_id, buttons=buttons)
        await cb.answer(f"✅ '{removed['text']}' o'chirildi!")
        await cb.message.edit_reply_markup(reply_markup=buttons_manager_kb(ad_id, buttons))
    else:
        await cb.answer("Tugma topilmadi!", show_alert=True)


# ─── REKLAMA PREVIEW ──────────────────────────────────────────────────────────

@router.callback_query(F.data.startswith("ad_stats:"))
async def cb_ad_stats(cb: CallbackQuery, db: Database):
    ad_id = int(cb.data.split(":")[1])
    stats = await db.get_send_stats(ad_id)
    sent = stats.get("sent", 0)
    failed = stats.get("failed", 0)
    total = sent + failed
    rate = f"{sent/total*100:.1f}%" if total > 0 else "N/A"

    await cb.message.edit_text(
        f"📊 <b>Reklama statistikasi</b>\n\n"
        f"✅ Muvaffaqiyatli: {sent}\n"
        f"❌ Xatoliklar: {failed}\n"
        f"📈 Muvaffaqiyat darajasi: {rate}\n"
        f"📦 Jami urinishlar: {total}",
        reply_markup=back_kb(f"ad_view:{ad_id}")
    )
    await cb.answer()
