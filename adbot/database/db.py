"""
🗄️ Database - SQLite bilan ishlash
"""

import aiosqlite
import json
import logging
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: str):
        self.db_path = db_path
        self.db: Optional[aiosqlite.Connection] = None

    async def init(self):
        """Databaseni ishga tushirish va jadvallar yaratish"""
        self.db = await aiosqlite.connect(self.db_path)
        self.db.row_factory = aiosqlite.Row
        await self.db.execute("PRAGMA journal_mode=WAL")
        await self.db.execute("PRAGMA foreign_keys=ON")
        await self._create_tables()
        await self.db.commit()
        logger.info("✅ Database tayyor")

    async def _create_tables(self):
        """Barcha jadvallarni yaratish"""

        # Foydalanuvchilar
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                full_name   TEXT,
                is_admin    INTEGER DEFAULT 0,
                is_banned   INTEGER DEFAULT 0,
                created_at  TEXT DEFAULT (datetime('now')),
                last_seen   TEXT DEFAULT (datetime('now'))
            )
        """)

        # Chatlar (kanal/guruhlar)
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS chats (
                chat_id      INTEGER PRIMARY KEY,
                title        TEXT NOT NULL,
                username     TEXT,
                chat_type    TEXT NOT NULL,
                member_count INTEGER DEFAULT 0,
                is_active    INTEGER DEFAULT 1,
                added_by     INTEGER,
                added_at     TEXT DEFAULT (datetime('now')),
                last_checked TEXT DEFAULT (datetime('now'))
            )
        """)

        # Reklama postlar
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS ads (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                title        TEXT NOT NULL,
                text         TEXT NOT NULL,
                media_type   TEXT,
                media_id     TEXT,
                buttons      TEXT DEFAULT '[]',
                status       TEXT DEFAULT 'draft',
                created_by   INTEGER,
                created_at   TEXT DEFAULT (datetime('now')),
                updated_at   TEXT DEFAULT (datetime('now'))
            )
        """)

        # Broadcast (tarqatish) jadvali
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS broadcasts (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_id        INTEGER NOT NULL,
                chat_ids     TEXT NOT NULL,
                interval_min INTEGER DEFAULT 60,
                start_time   TEXT,
                end_time     TEXT,
                is_active    INTEGER DEFAULT 1,
                is_recurring INTEGER DEFAULT 0,
                created_by   INTEGER,
                created_at   TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (ad_id) REFERENCES ads(id)
            )
        """)

        # Yuborilgan xabarlar logi
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS send_logs (
                id           INTEGER PRIMARY KEY AUTOINCREMENT,
                broadcast_id INTEGER,
                ad_id        INTEGER,
                chat_id      INTEGER,
                message_id   INTEGER,
                status       TEXT DEFAULT 'sent',
                error_text   TEXT,
                sent_at      TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (broadcast_id) REFERENCES broadcasts(id)
            )
        """)

        # Statistika
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                ad_id       INTEGER,
                chat_id     INTEGER,
                views       INTEGER DEFAULT 0,
                clicks      INTEGER DEFAULT 0,
                date        TEXT DEFAULT (date('now')),
                FOREIGN KEY (ad_id) REFERENCES ads(id)
            )
        """)

        # Bot sozlamalari
        await self.db.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key     TEXT PRIMARY KEY,
                value   TEXT,
                updated_at TEXT DEFAULT (datetime('now'))
            )
        """)

        logger.info("✅ Jadvallar yaratildi")

    # ─── USERS ───────────────────────────────────────────────

    async def get_user(self, user_id: int) -> Optional[Dict]:
        async with self.db.execute(
            "SELECT * FROM users WHERE user_id = ?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def upsert_user(self, user_id: int, username: str, full_name: str, is_admin: bool = False):
        await self.db.execute("""
            INSERT INTO users (user_id, username, full_name, is_admin, last_seen)
            VALUES (?, ?, ?, ?, datetime('now'))
            ON CONFLICT(user_id) DO UPDATE SET
                username  = excluded.username,
                full_name = excluded.full_name,
                last_seen = datetime('now')
        """, (user_id, username, full_name, int(is_admin)))
        await self.db.commit()

    async def ban_user(self, user_id: int) -> bool:
        await self.db.execute("UPDATE users SET is_banned = 1 WHERE user_id = ?", (user_id,))
        await self.db.commit()
        return True

    async def unban_user(self, user_id: int) -> bool:
        await self.db.execute("UPDATE users SET is_banned = 0 WHERE user_id = ?", (user_id,))
        await self.db.commit()
        return True

    async def get_all_users(self) -> List[Dict]:
        async with self.db.execute("SELECT * FROM users ORDER BY created_at DESC") as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def get_user_count(self) -> int:
        async with self.db.execute("SELECT COUNT(*) FROM users") as cur:
            r = await cur.fetchone()
            return r[0]

    # ─── CHATS ───────────────────────────────────────────────

    async def add_chat(self, chat_id: int, title: str, username: str,
                       chat_type: str, member_count: int, added_by: int) -> bool:
        try:
            await self.db.execute("""
                INSERT INTO chats (chat_id, title, username, chat_type, member_count, added_by)
                VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET
                    title        = excluded.title,
                    username     = excluded.username,
                    member_count = excluded.member_count,
                    is_active    = 1,
                    last_checked = datetime('now')
            """, (chat_id, title, username, chat_type, member_count, added_by))
            await self.db.commit()
            return True
        except Exception as e:
            logger.error(f"Chat qo'shishda xato: {e}")
            return False

    async def remove_chat(self, chat_id: int) -> bool:
        await self.db.execute("UPDATE chats SET is_active = 0 WHERE chat_id = ?", (chat_id,))
        await self.db.commit()
        return True

    async def get_chat(self, chat_id: int) -> Optional[Dict]:
        async with self.db.execute(
            "SELECT * FROM chats WHERE chat_id = ?", (chat_id,)
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None

    async def get_all_chats(self, active_only: bool = True) -> List[Dict]:
        q = "SELECT * FROM chats"
        if active_only:
            q += " WHERE is_active = 1"
        q += " ORDER BY title"
        async with self.db.execute(q) as cur:
            return [dict(r) for r in await cur.fetchall()]

    async def get_chat_count(self) -> int:
        async with self.db.execute("SELECT COUNT(*) FROM chats WHERE is_active = 1") as cur:
            r = await cur.fetchone()
            return r[0]

    async def update_chat_members(self, chat_id: int, count: int):
        await self.db.execute(
            "UPDATE chats SET member_count = ?, last_checked = datetime('now') WHERE chat_id = ?",
            (count, chat_id)
        )
        await self.db.commit()

    # ─── ADS ─────────────────────────────────────────────────

    async def create_ad(self, title: str, text: str, created_by: int,
                        media_type: str = None, media_id: str = None,
                        buttons: list = None) -> int:
        buttons_json = json.dumps(buttons or [], ensure_ascii=False)
        async with self.db.execute("""
            INSERT INTO ads (title, text, media_type, media_id, buttons, created_by)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (title, text, media_type, media_id, buttons_json, created_by)) as cur:
            ad_id = cur.lastrowid
        await self.db.commit()
        return ad_id

    async def get_ad(self, ad_id: int) -> Optional[Dict]:
        async with self.db.execute("SELECT * FROM ads WHERE id = ?", (ad_id,)) as cur:
            row = await cur.fetchone()
            if row:
                d = dict(row)
                d["buttons"] = json.loads(d["buttons"] or "[]")
                return d
            return None

    async def get_all_ads(self) -> List[Dict]:
        async with self.db.execute("SELECT * FROM ads ORDER BY created_at DESC") as cur:
            rows = await cur.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["buttons"] = json.loads(d["buttons"] or "[]")
                result.append(d)
            return result

    async def update_ad(self, ad_id: int, **kwargs):
        if "buttons" in kwargs:
            kwargs["buttons"] = json.dumps(kwargs["buttons"], ensure_ascii=False)
        kwargs["updated_at"] = datetime.now().isoformat()
        sets = ", ".join(f"{k} = ?" for k in kwargs)
        vals = list(kwargs.values()) + [ad_id]
        await self.db.execute(f"UPDATE ads SET {sets} WHERE id = ?", vals)
        await self.db.commit()

    async def delete_ad(self, ad_id: int) -> bool:
        await self.db.execute("DELETE FROM ads WHERE id = ?", (ad_id,))
        await self.db.commit()
        return True

    async def get_ad_count(self) -> int:
        async with self.db.execute("SELECT COUNT(*) FROM ads") as cur:
            r = await cur.fetchone()
            return r[0]

    # ─── BROADCASTS ──────────────────────────────────────────

    async def create_broadcast(self, ad_id: int, chat_ids: list, interval_min: int,
                                start_time: str, end_time: str, is_recurring: bool,
                                created_by: int) -> int:
        async with self.db.execute("""
            INSERT INTO broadcasts (ad_id, chat_ids, interval_min, start_time, end_time,
                                    is_recurring, created_by)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (ad_id, json.dumps(chat_ids), interval_min, start_time, end_time,
              int(is_recurring), created_by)) as cur:
            bid = cur.lastrowid
        await self.db.commit()
        return bid

    async def get_broadcast(self, bid: int) -> Optional[Dict]:
        async with self.db.execute("SELECT * FROM broadcasts WHERE id = ?", (bid,)) as cur:
            row = await cur.fetchone()
            if row:
                d = dict(row)
                d["chat_ids"] = json.loads(d["chat_ids"])
                return d
            return None

    async def get_active_broadcasts(self) -> List[Dict]:
        async with self.db.execute(
            "SELECT * FROM broadcasts WHERE is_active = 1"
        ) as cur:
            rows = await cur.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["chat_ids"] = json.loads(d["chat_ids"])
                result.append(d)
            return result

    async def get_all_broadcasts(self) -> List[Dict]:
        async with self.db.execute(
            "SELECT b.*, a.title as ad_title FROM broadcasts b "
            "LEFT JOIN ads a ON b.ad_id = a.id ORDER BY b.created_at DESC"
        ) as cur:
            rows = await cur.fetchall()
            result = []
            for r in rows:
                d = dict(r)
                d["chat_ids"] = json.loads(d["chat_ids"])
                result.append(d)
            return result

    async def toggle_broadcast(self, bid: int, active: bool) -> bool:
        await self.db.execute(
            "UPDATE broadcasts SET is_active = ? WHERE id = ?", (int(active), bid)
        )
        await self.db.commit()
        return True

    async def delete_broadcast(self, bid: int) -> bool:
        await self.db.execute("DELETE FROM broadcasts WHERE id = ?", (bid,))
        await self.db.commit()
        return True

    # ─── SEND LOGS ───────────────────────────────────────────

    async def log_send(self, broadcast_id: int, ad_id: int, chat_id: int,
                       message_id: int = None, status: str = "sent", error: str = None):
        await self.db.execute("""
            INSERT INTO send_logs (broadcast_id, ad_id, chat_id, message_id, status, error_text)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (broadcast_id, ad_id, chat_id, message_id, status, error))
        await self.db.commit()

    async def get_send_stats(self, ad_id: int = None) -> Dict:
        if ad_id:
            q = "SELECT status, COUNT(*) as cnt FROM send_logs WHERE ad_id = ? GROUP BY status"
            args = (ad_id,)
        else:
            q = "SELECT status, COUNT(*) as cnt FROM send_logs GROUP BY status"
            args = ()
        async with self.db.execute(q, args) as cur:
            rows = await cur.fetchall()
            return {r["status"]: r["cnt"] for r in rows}

    async def get_recent_logs(self, limit: int = 50) -> List[Dict]:
        async with self.db.execute(
            "SELECT l.*, c.title as chat_title FROM send_logs l "
            "LEFT JOIN chats c ON l.chat_id = c.chat_id "
            "ORDER BY l.sent_at DESC LIMIT ?", (limit,)
        ) as cur:
            return [dict(r) for r in await cur.fetchall()]

    # ─── SETTINGS ────────────────────────────────────────────

    async def get_setting(self, key: str, default: str = None) -> Optional[str]:
        async with self.db.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ) as cur:
            row = await cur.fetchone()
            return row["value"] if row else default

    async def set_setting(self, key: str, value: str):
        await self.db.execute("""
            INSERT INTO settings (key, value) VALUES (?, ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value,
                                           updated_at = datetime('now')
        """, (key, value))
        await self.db.commit()

    # ─── GLOBAL STATS ────────────────────────────────────────

    async def get_global_stats(self) -> Dict:
        stats = {}
        async with self.db.execute("SELECT COUNT(*) FROM users") as c:
            stats["users"] = (await c.fetchone())[0]
        async with self.db.execute("SELECT COUNT(*) FROM chats WHERE is_active=1") as c:
            stats["chats"] = (await c.fetchone())[0]
        async with self.db.execute("SELECT COUNT(*) FROM ads") as c:
            stats["ads"] = (await c.fetchone())[0]
        async with self.db.execute("SELECT COUNT(*) FROM broadcasts WHERE is_active=1") as c:
            stats["active_broadcasts"] = (await c.fetchone())[0]
        async with self.db.execute("SELECT COUNT(*) FROM send_logs WHERE status='sent'") as c:
            stats["total_sent"] = (await c.fetchone())[0]
        async with self.db.execute("SELECT COUNT(*) FROM send_logs WHERE status='failed'") as c:
            stats["total_failed"] = (await c.fetchone())[0]
        return stats

    async def close(self):
        if self.db:
            await self.db.close()
