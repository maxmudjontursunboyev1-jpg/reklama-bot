"""
🛠 Yordamchi funksiyalar
"""

import logging
from datetime import datetime
from typing import Optional
from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup

logger = logging.getLogger(__name__)


async def send_ad_message(bot: Bot, chat_id: int, ad: dict) -> int:
    """
    Reklamani chatga yuborish - media tur bo'yicha
    Returns: message_id
    """
    buttons = ad.get("buttons", [])
    reply_markup = _build_inline_kb(buttons) if buttons else None

    media_type = ad.get("media_type")
    media_id = ad.get("media_id")
    text = ad["text"]

    if not media_type or not media_id:
        msg = await bot.send_message(
            chat_id, text, reply_markup=reply_markup
        )
    elif media_type == "photo":
        msg = await bot.send_photo(
            chat_id, media_id, caption=text, reply_markup=reply_markup
        )
    elif media_type == "video":
        msg = await bot.send_video(
            chat_id, media_id, caption=text, reply_markup=reply_markup
        )
    elif media_type == "document":
        msg = await bot.send_document(
            chat_id, media_id, caption=text, reply_markup=reply_markup
        )
    elif media_type == "animation":
        msg = await bot.send_animation(
            chat_id, media_id, caption=text, reply_markup=reply_markup
        )
    elif media_type == "audio":
        msg = await bot.send_audio(
            chat_id, media_id, caption=text, reply_markup=reply_markup
        )
    else:
        msg = await bot.send_message(
            chat_id, text, reply_markup=reply_markup
        )

    return msg.message_id


def _build_inline_kb(buttons: list) -> Optional[InlineKeyboardMarkup]:
    """Inline klaviatura yaratish"""
    if not buttons:
        return None

    from aiogram.utils.keyboard import InlineKeyboardBuilder
    builder = InlineKeyboardBuilder()
    for btn in buttons:
        try:
            builder.button(text=btn["text"], url=btn["url"])
        except Exception as e:
            logger.warning(f"Tugma qo'shishda xato: {e}")

    if not builder.buttons:
        return None

    # 2 li qatorlarda joylash
    rows = []
    btn_list = builder.buttons
    for i in range(0, len(btn_list), 2):
        rows.append(len(btn_list[i:i+2]))

    builder.adjust(*rows)
    return builder.as_markup()


def format_datetime(dt_str: str) -> str:
    """ISO datetime ni chiroyli formatga o'girish"""
    try:
        dt = datetime.fromisoformat(dt_str)
        return dt.strftime("%d.%m.%Y %H:%M")
    except:
        return dt_str or "N/A"


def truncate_text(text: str, max_len: int = 100) -> str:
    """Matnni qisqartirish"""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def format_number(num: int) -> str:
    """Raqamni formatlash: 1000000 → 1,000,000"""
    return f"{num:,}"
