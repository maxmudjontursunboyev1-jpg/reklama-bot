"""
🔐 Autentifikatsiya middleware
"""

import logging
from typing import Any, Awaitable, Callable, Dict
from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from config import config
from database.db import Database

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseMiddleware):
    def __init__(self, db: Database):
        self.db = db

    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user:
            # Foydalanuvchini saqlash
            is_admin = config.is_admin(user.id)
            await self.db.upsert_user(
                user.id,
                user.username or "",
                user.full_name or "",
                is_admin=is_admin
            )

            # Banlangan foydalanuvchini bloklash
            db_user = await self.db.get_user(user.id)
            if db_user and db_user.get("is_banned") and not is_admin:
                if isinstance(event, Message):
                    await event.answer("🚫 Siz bloklangansiz.")
                elif isinstance(event, CallbackQuery):
                    await event.answer("🚫 Siz bloklangansiz.", show_alert=True)
                return

        return await handler(event, data)
