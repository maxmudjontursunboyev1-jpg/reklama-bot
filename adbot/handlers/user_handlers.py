"""
👤 Oddiy foydalanuvchi handlerlar
"""

import logging
from aiogram import Router, F
from aiogram.filters import CommandStart
from aiogram.types import Message

from database.db import Database
from config import config

logger = logging.getLogger(__name__)
router = Router()


@router.message(CommandStart())
async def user_start(msg: Message, db: Database):
    """Admin bo'lmagan foydalanuvchilar uchun"""
    if config.is_admin(msg.from_user.id):
        return  # Admin handler hal qiladi

    await db.upsert_user(
        msg.from_user.id,
        msg.from_user.username or "",
        msg.from_user.full_name or ""
    )

    await msg.answer(
        f"👋 Salom, <b>{msg.from_user.first_name}</b>!\n\n"
        f"Bu bot faqat adminlar uchun mo'ljallangan."
    )


@router.message()
async def catch_all(msg: Message, db: Database):
    """Barcha boshqa xabarlarni ushlash"""
    if config.is_admin(msg.from_user.id):
        return  # Admin handlerlarga o'tkazib yuborish

    await db.upsert_user(
        msg.from_user.id,
        msg.from_user.username or "",
        msg.from_user.full_name or ""
    )
