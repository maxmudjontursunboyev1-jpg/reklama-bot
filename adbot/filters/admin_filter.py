"""
🔐 Admin filter
"""

from aiogram.filters import BaseFilter
from aiogram.types import Message, CallbackQuery
from config import config


class IsAdmin(BaseFilter):
    async def __call__(self, event) -> bool:
        user = None
        if isinstance(event, Message):
            user = event.from_user
        elif isinstance(event, CallbackQuery):
            user = event.from_user

        if user:
            return config.is_admin(user.id)
        return False
