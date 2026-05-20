"""
⌨️ Barcha keyboard va tugmalar
"""

from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove
)
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from typing import List, Dict, Optional


# ─── REPLY KEYBOARDS ──────────────────────────────────────────────────────────

def main_menu_kb() -> ReplyKeyboardMarkup:
    """Asosiy menyu (admin)"""
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="📢 Reklamalar"),
        KeyboardButton(text="📡 Chatlar"),
    )
    builder.row(
        KeyboardButton(text="🕐 Scheduler"),
        KeyboardButton(text="📊 Statistika"),
    )
    builder.row(
        KeyboardButton(text="⚙️ Sozlamalar"),
        KeyboardButton(text="👥 Foydalanuvchilar"),
    )
    return builder.as_markup(resize_keyboard=True)


def cancel_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.add(KeyboardButton(text="❌ Bekor qilish"))
    return builder.as_markup(resize_keyboard=True)


def skip_cancel_kb() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    builder.row(
        KeyboardButton(text="⏭ O'tkazib yuborish"),
        KeyboardButton(text="❌ Bekor qilish"),
    )
    return builder.as_markup(resize_keyboard=True)


# ─── INLINE KEYBOARDS ─────────────────────────────────────────────────────────

def ads_list_kb(ads: list) -> InlineKeyboardMarkup:
    """Reklamalar ro'yxati"""
    builder = InlineKeyboardBuilder()
    for ad in ads:
        status_icon = {"draft": "📝", "active": "✅", "paused": "⏸"}.get(ad["status"], "📌")
        builder.button(
            text=f"{status_icon} {ad['title'][:30]}",
            callback_data=f"ad_view:{ad['id']}"
        )
    builder.button(text="➕ Yangi reklama", callback_data="ad_create")
    builder.button(text="🔙 Orqaga", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()


def ad_detail_kb(ad_id: int, status: str) -> InlineKeyboardMarkup:
    """Reklama detail sahifasi"""
    builder = InlineKeyboardBuilder()
    builder.button(text="✏️ Tahrirlash", callback_data=f"ad_edit:{ad_id}")
    builder.button(text="📤 Yuborish", callback_data=f"ad_send:{ad_id}")
    builder.button(text="🕐 Jadvalga qo'shish", callback_data=f"ad_schedule:{ad_id}")
    builder.button(text="🔘 Inline tugmalar", callback_data=f"ad_buttons:{ad_id}")
    if status == "active":
        builder.button(text="⏸ To'xtatish", callback_data=f"ad_pause:{ad_id}")
    else:
        builder.button(text="▶️ Faollashtirish", callback_data=f"ad_activate:{ad_id}")
    builder.button(text="📊 Statistika", callback_data=f"ad_stats:{ad_id}")
    builder.button(text="🗑 O'chirish", callback_data=f"ad_delete:{ad_id}")
    builder.button(text="🔙 Orqaga", callback_data="back_ads")
    builder.adjust(2, 2, 2, 1, 1)
    return builder.as_markup()


def ad_edit_kb(ad_id: int) -> InlineKeyboardMarkup:
    """Reklama tahrirlash"""
    builder = InlineKeyboardBuilder()
    builder.button(text="📌 Sarlavha", callback_data=f"edit_title:{ad_id}")
    builder.button(text="📝 Matn", callback_data=f"edit_text:{ad_id}")
    builder.button(text="🖼 Media", callback_data=f"edit_media:{ad_id}")
    builder.button(text="🔘 Tugmalar", callback_data=f"ad_buttons:{ad_id}")
    builder.button(text="🔙 Orqaga", callback_data=f"ad_view:{ad_id}")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def chats_list_kb(chats: list, page: int = 0, page_size: int = 8) -> InlineKeyboardMarkup:
    """Chatlar ro'yxati (sahifalash bilan)"""
    builder = InlineKeyboardBuilder()
    start = page * page_size
    end = start + page_size
    page_chats = chats[start:end]

    for chat in page_chats:
        icon = "📢" if chat["chat_type"] == "channel" else "👥"
        members = f" ({chat['member_count']:,})" if chat.get("member_count") else ""
        status = "✅" if chat["is_active"] else "❌"
        builder.button(
            text=f"{status} {icon} {chat['title'][:25]}{members}",
            callback_data=f"chat_view:{chat['chat_id']}"
        )

    # Navigatsiya
    nav_buttons = []
    if page > 0:
        nav_buttons.append(
            InlineKeyboardButton(text="⬅️", callback_data=f"chats_page:{page-1}")
        )
    nav_buttons.append(
        InlineKeyboardButton(
            text=f"📄 {page+1}/{max(1, (len(chats)-1)//page_size + 1)}",
            callback_data="noop"
        )
    )
    if end < len(chats):
        nav_buttons.append(
            InlineKeyboardButton(text="➡️", callback_data=f"chats_page:{page+1}")
        )

    builder.adjust(1)
    kb = builder.as_markup()
    if nav_buttons:
        kb.inline_keyboard.append(nav_buttons)

    kb.inline_keyboard.append([
        InlineKeyboardButton(text="➕ Chat qo'shish", callback_data="chat_add"),
        InlineKeyboardButton(text="🔄 Yangilash", callback_data="chats_refresh"),
    ])
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="🗑 Barchasini tozalash", callback_data="chats_clear"),
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main"),
    ])
    return kb


def chat_detail_kb(chat_id: int, is_active: bool) -> InlineKeyboardMarkup:
    """Chat detail"""
    builder = InlineKeyboardBuilder()
    builder.button(text="🔄 Yangilash", callback_data=f"chat_refresh:{chat_id}")
    if is_active:
        builder.button(text="⏸ O'chirish", callback_data=f"chat_deactivate:{chat_id}")
    else:
        builder.button(text="▶️ Yoqish", callback_data=f"chat_activate:{chat_id}")
    builder.button(text="📢 Reklama yuborish", callback_data=f"chat_send_ad:{chat_id}")
    builder.button(text="🗑 O'chirish", callback_data=f"chat_delete:{chat_id}")
    builder.button(text="🔙 Orqaga", callback_data="back_chats")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def chat_selector_kb(chats: list, selected: list = None, action: str = "broadcast") -> InlineKeyboardMarkup:
    """Chat tanlash (broadcast uchun)"""
    selected = selected or []
    builder = InlineKeyboardBuilder()

    for chat in chats:
        icon = "✅" if chat["chat_id"] in selected else "☑️"
        chat_icon = "📢" if chat["chat_type"] == "channel" else "👥"
        builder.button(
            text=f"{icon} {chat_icon} {chat['title'][:25]}",
            callback_data=f"select_chat:{chat['chat_id']}:{action}"
        )

    builder.button(
        text=f"✅ Barchasini tanlash ({len(chats)})",
        callback_data=f"select_all_chats:{action}"
    )
    builder.button(
        text="❌ Barchasini bekor qilish",
        callback_data=f"deselect_all_chats:{action}"
    )
    builder.button(
        text=f"▶️ Davom etish ({len(selected)} tanlangan)",
        callback_data=f"confirm_chats:{action}"
    )
    builder.button(text="🔙 Bekor qilish", callback_data="back_ads")
    builder.adjust(1)
    return builder.as_markup()


def broadcast_list_kb(broadcasts: list) -> InlineKeyboardMarkup:
    """Broadcast ro'yxati"""
    builder = InlineKeyboardBuilder()
    for b in broadcasts:
        status = "✅" if b["is_active"] else "⏸"
        recurring = "🔄" if b["is_recurring"] else "1️⃣"
        title = b.get("ad_title", f"ID:{b['id']}")[:20]
        builder.button(
            text=f"{status} {recurring} {title}",
            callback_data=f"broadcast_view:{b['id']}"
        )
    builder.button(text="➕ Yangi jadval", callback_data="broadcast_create")
    builder.button(text="🔙 Orqaga", callback_data="back_main")
    builder.adjust(1)
    return builder.as_markup()


def broadcast_detail_kb(bid: int, is_active: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_active:
        builder.button(text="⏸ To'xtatish", callback_data=f"broadcast_stop:{bid}")
    else:
        builder.button(text="▶️ Ishga tushirish", callback_data=f"broadcast_start:{bid}")
    builder.button(text="▶️ Hozir yuborish", callback_data=f"broadcast_now:{bid}")
    builder.button(text="📊 Statistika", callback_data=f"broadcast_stats:{bid}")
    builder.button(text="🗑 O'chirish", callback_data=f"broadcast_delete:{bid}")
    builder.button(text="🔙 Orqaga", callback_data="back_scheduler")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def send_confirm_kb(ad_id: int, chat_ids_str: str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="✅ Ha, yuborish", callback_data=f"confirm_send:{ad_id}:{chat_ids_str}")
    builder.button(text="❌ Bekor qilish", callback_data=f"ad_view:{ad_id}")
    builder.adjust(2)
    return builder.as_markup()


def confirm_delete_kb(item_type: str, item_id: int) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🗑 Ha, o'chirish", callback_data=f"confirm_delete:{item_type}:{item_id}")
    builder.button(text="❌ Bekor qilish", callback_data=f"{item_type}_view:{item_id}")
    builder.adjust(2)
    return builder.as_markup()


def buttons_manager_kb(ad_id: int, buttons: list) -> InlineKeyboardMarkup:
    """Reklama inline tugmalarini boshqarish"""
    builder = InlineKeyboardBuilder()
    for i, btn in enumerate(buttons):
        builder.button(
            text=f"🔘 {btn['text'][:20]} → {btn['url'][:20]}",
            callback_data=f"btn_edit:{ad_id}:{i}"
        )
        builder.button(text="🗑", callback_data=f"btn_delete:{ad_id}:{i}")

    builder.button(text="➕ Tugma qo'shish", callback_data=f"btn_add:{ad_id}")
    builder.button(text="🔙 Orqaga", callback_data=f"ad_view:{ad_id}")
    builder.adjust(2 if buttons else 1)
    if buttons:
        # Oxirgi 2 tugma alohida qator
        kb = builder.as_markup()
        return kb
    return builder.as_markup()


def stats_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="📊 Umumiy statistika", callback_data="stats_global")
    builder.button(text="📢 Reklamalar bo'yicha", callback_data="stats_by_ads")
    builder.button(text="📡 Chatlar bo'yicha", callback_data="stats_by_chats")
    builder.button(text="📝 So'nggi loglar", callback_data="stats_logs")
    builder.button(text="🔙 Orqaga", callback_data="back_main")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def settings_kb() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="⏱ Default interval", callback_data="setting_interval")
    builder.button(text="📬 Xabar formati", callback_data="setting_format")
    builder.button(text="🔕 Xabar rejimi", callback_data="setting_silent")
    builder.button(text="🌐 Bot haqida", callback_data="setting_about")
    builder.button(text="🔙 Orqaga", callback_data="back_main")
    builder.adjust(2, 2, 1)
    return builder.as_markup()


def users_list_kb(users: list, page: int = 0) -> InlineKeyboardMarkup:
    """Foydalanuvchilar ro'yxati"""
    builder = InlineKeyboardBuilder()
    page_size = 10
    start = page * page_size
    page_users = users[start:start + page_size]

    for u in page_users:
        icon = "👑" if u["is_admin"] else ("🚫" if u["is_banned"] else "👤")
        name = u.get("full_name") or u.get("username") or str(u["user_id"])
        builder.button(
            text=f"{icon} {name[:25]}",
            callback_data=f"user_view:{u['user_id']}"
        )

    nav = []
    if page > 0:
        nav.append(InlineKeyboardButton(text="⬅️", callback_data=f"users_page:{page-1}"))
    total_pages = max(1, (len(users) - 1) // page_size + 1)
    nav.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="noop"))
    if start + page_size < len(users):
        nav.append(InlineKeyboardButton(text="➡️", callback_data=f"users_page:{page+1}"))

    builder.adjust(1)
    kb = builder.as_markup()
    if nav:
        kb.inline_keyboard.append(nav)
    kb.inline_keyboard.append([
        InlineKeyboardButton(text="📣 Barchaga xabar", callback_data="users_broadcast"),
        InlineKeyboardButton(text="🔙 Orqaga", callback_data="back_main"),
    ])
    return kb


def user_detail_kb(user_id: int, is_banned: bool, is_admin: bool) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if is_banned:
        builder.button(text="✅ Ban'dan chiqarish", callback_data=f"user_unban:{user_id}")
    else:
        builder.button(text="🚫 Banlash", callback_data=f"user_ban:{user_id}")
    if not is_admin:
        builder.button(text="👑 Admin qilish", callback_data=f"user_make_admin:{user_id}")
    builder.button(text="💬 Xabar yuborish", callback_data=f"user_message:{user_id}")
    builder.button(text="🔙 Orqaga", callback_data="back_users")
    builder.adjust(2, 1, 1)
    return builder.as_markup()


def back_kb(callback: str = "back_main") -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.button(text="🔙 Orqaga", callback_data=callback)
    return builder.as_markup()


def ad_preview_buttons(buttons: list) -> Optional[InlineKeyboardMarkup]:
    """Reklama previewidagi real inline tugmalar"""
    if not buttons:
        return None
    builder = InlineKeyboardBuilder()
    for btn in buttons:
        try:
            builder.button(text=btn["text"], url=btn["url"])
        except Exception:
            pass
    builder.adjust(2)
    return builder.as_markup()
