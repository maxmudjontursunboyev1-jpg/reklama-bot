"""
⚙️ Bot konfiguratsiyasi
"""

import os
from dataclasses import dataclass, field
from typing import List
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Config:
    # Bot token (BotFather dan oling)
    BOT_TOKEN: str = os.getenv("BOT_TOKEN", "YOUR_BOT_TOKEN_HERE")

    # Admin ID lari (vergul bilan ajrating: 123456,789012)
    ADMIN_IDS: List[int] = field(default_factory=lambda: [
        int(x.strip()) for x in os.getenv("ADMIN_IDS", "123456789").split(",")
        if x.strip().isdigit()
    ])

    # Database
    DATABASE_PATH: str = os.getenv("DATABASE_PATH", "adbot.db")

    # Bot sozlamalari
    MAX_AD_TEXT_LENGTH: int = 4096
    MAX_INLINE_BUTTONS: int = 10
    MAX_CHATS_PER_AD: int = 100
    DEFAULT_INTERVAL_MINUTES: int = 60
    MIN_INTERVAL_MINUTES: int = 5

    # Throttling
    THROTTLE_RATE: float = 0.5

    # Fayllar
    MEDIA_DIR: str = "media"

    # Kanal/Guruh turlari
    CHAT_TYPES = ["channel", "group", "supergroup"]

    def is_admin(self, user_id: int) -> bool:
        return user_id in self.ADMIN_IDS


config = Config()

# Media papkasini yaratish
os.makedirs(config.MEDIA_DIR, exist_ok=True)
