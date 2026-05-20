"""
⏰ Ad Scheduler - avtomatik reklama yuborish xizmati
"""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from aiogram import Bot

from database.db import Database
from utils.helpers import send_ad_message

logger = logging.getLogger(__name__)


class AdScheduler:
    def __init__(self, bot: Bot, db: Database):
        self.bot = bot
        self.db = db
        self._task: Optional[asyncio.Task] = None
        self._running = False

    async def start(self):
        self._running = True
        self._task = asyncio.create_task(self._run())
        logger.info("⏰ Scheduler ishga tushdi")

    async def stop(self):
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("⏰ Scheduler to'xtatildi")

    async def _run(self):
        """Asosiy scheduler loop"""
        while self._running:
            try:
                await self._check_broadcasts()
            except Exception as e:
                logger.error(f"Scheduler xatosi: {e}")
            await asyncio.sleep(60)  # Har daqiqada tekshirish

    async def _check_broadcasts(self):
        """Aktiv broadcastlarni tekshirish va yuborish"""
        broadcasts = await self.db.get_active_broadcasts()
        now = datetime.now()

        for b in broadcasts:
            try:
                await self._process_broadcast(b, now)
            except Exception as e:
                logger.error(f"Broadcast {b['id']} xatosi: {e}")

    async def _process_broadcast(self, broadcast: dict, now: datetime):
        bid = broadcast["id"]
        interval = broadcast["interval_min"]

        # Tugash vaqtini tekshirish
        if broadcast.get("end_time"):
            try:
                end_dt = datetime.strptime(broadcast["end_time"], "%Y-%m-%d %H:%M")
                if now > end_dt:
                    await self.db.toggle_broadcast(bid, False)
                    logger.info(f"Broadcast {bid} vaqti tugadi, o'chirildi")
                    return
            except ValueError:
                pass

        # Boshlash vaqtini tekshirish
        if broadcast.get("start_time"):
            try:
                start_dt = datetime.strptime(broadcast["start_time"], "%Y-%m-%d %H:%M")
                if now < start_dt:
                    return  # Hali vaqt kelmadi
            except ValueError:
                pass

        # So'nggi yuborish vaqtini tekshirish
        last_sent = await self._get_last_sent_time(bid)
        if last_sent:
            elapsed = (now - last_sent).total_seconds() / 60
            if elapsed < interval:
                return  # Hali vaqt kelmadi

        # Yuborish
        ad = await self.db.get_ad(broadcast["ad_id"])
        if not ad:
            await self.db.toggle_broadcast(bid, False)
            return

        if ad["status"] == "paused":
            return

        success = failed = 0
        for chat_id in broadcast["chat_ids"]:
            try:
                msg_id = await send_ad_message(self.bot, chat_id, ad)
                await self.db.log_send(bid, broadcast["ad_id"], chat_id, msg_id, "sent")
                success += 1
                await asyncio.sleep(0.05)  # Flood limit
            except Exception as e:
                await self.db.log_send(bid, broadcast["ad_id"], chat_id, status="failed", error=str(e))
                failed += 1
                logger.warning(f"Chat {chat_id} ga yuborishda xato: {e}")

        logger.info(f"Broadcast {bid}: ✅{success} ❌{failed}")

        # Bir martalik bo'lsa o'chirish
        if not broadcast["is_recurring"]:
            await self.db.toggle_broadcast(bid, False)

    async def _get_last_sent_time(self, broadcast_id: int) -> Optional[datetime]:
        """Broadcast uchun so'nggi yuborish vaqtini olish"""
        async with self.db.db.execute(
            "SELECT MAX(sent_at) as last FROM send_logs WHERE broadcast_id = ? AND status = 'sent'",
            (broadcast_id,)
        ) as cur:
            row = await cur.fetchone()
            if row and row["last"]:
                try:
                    return datetime.fromisoformat(row["last"])
                except ValueError:
                    return None
        return None
