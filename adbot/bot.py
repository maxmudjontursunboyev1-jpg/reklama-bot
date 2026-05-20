#!/usr/bin/env python3
"""
🚀 Professional Telegram Advertising Bot
Author: AdBot Pro
Version: 2.0.0
"""

import asyncio
import logging
import os
from datetime import datetime

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

from config import config
from database.db import Database
from handlers import (
    admin_handlers,
    ad_handlers,
    broadcast_handlers,
    chat_handlers,
    scheduler_handlers,
    stats_handlers,
    user_handlers,
)
from middlewares.auth_middleware import AuthMiddleware
from middlewares.throttle_middleware import ThrottlingMiddleware
from services.scheduler import AdScheduler
from utils.logger import setup_logger

logger = setup_logger(__name__)


async def on_startup(bot: Bot, db: Database):
    """Bot ishga tushganda"""
    await db.init()
    me = await bot.get_me()
    logger.info(f"✅ Bot ishga tushdi: @{me.username} (ID: {me.id})")

    # Admin(lar)ga xabar yuborish
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🟢 <b>AdBot Pro ishga tushdi!</b>\n\n"
                f"🤖 Bot: @{me.username}\n"
                f"📅 Vaqt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
                f"🔧 Version: 2.0.0",
            )
        except Exception as e:
            logger.warning(f"Admin {admin_id} ga xabar yuborib bo'lmadi: {e}")


async def on_shutdown(bot: Bot):
    """Bot o'chganda"""
    logger.info("🔴 Bot o'chdi")
    for admin_id in config.ADMIN_IDS:
        try:
            await bot.send_message(admin_id, "🔴 <b>AdBot Pro o'chdi!</b>")
        except:
            pass


async def main():
    # Bot va Dispatcher yaratish
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML),
    )
    dp = Dispatcher(storage=MemoryStorage())

    # Database
    db = Database(config.DATABASE_PATH)

    # Scheduler
    scheduler = AdScheduler(bot, db)

    # Middlewares
    dp.message.middleware(AuthMiddleware(db))
    dp.message.middleware(ThrottlingMiddleware(rate_limit=0.5))
    dp.callback_query.middleware(AuthMiddleware(db))

    # dp ga db va scheduler ni uzatish
    dp["db"] = db
    dp["scheduler"] = scheduler

    # Handlerlarni ro'yxatdan o'tkazish
    dp.include_router(user_handlers.router)
    dp.include_router(admin_handlers.router)
    dp.include_router(chat_handlers.router)
    dp.include_router(ad_handlers.router)
    dp.include_router(broadcast_handlers.router)
    dp.include_router(scheduler_handlers.router)
    dp.include_router(stats_handlers.router)

    # Startup/Shutdown
    dp.startup.register(lambda: on_startup(bot, db))
    dp.shutdown.register(lambda: on_shutdown(bot))

    # Scheduler ishga tushirish
    await scheduler.start()

    try:
        logger.info("🚀 Bot polling boshlandi...")
        await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
    finally:
        await scheduler.stop()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
