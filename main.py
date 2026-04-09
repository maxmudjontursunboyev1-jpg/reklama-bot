# ═══════════════════════════════════════════════════════════════
# GOOGLE SHEETS BILAN ISHLASH (Render va lokal muhit uchun moslashgan)
# ═══════════════════════════════════════════════════════════════

import json
import os
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

SPREADSHEET_NAME = os.getenv("SPREADSHEET_NAME", "AdsManagerBot")

def get_google_credentials():
    """Render yoki lokal muhitga qarab credentialni olish"""
    scopes = [
        "[googleapis.com](https://www.googleapis.com/auth/spreadsheets)",
        "[googleapis.com](https://www.googleapis.com/auth/drive)"
    ]

    # Render server uchun
    secret_path = "/etc/secrets/GOOGLE_CREDENTIALS"

    try:
        if os.path.exists(secret_path):
            # Render Secret File
            creds = Credentials.from_service_account_file(secret_path, scopes=scopes)
            logger.info("Render: GOOGLE_CREDENTIALS fayldan yuklandi.")
        else:
            # Lokal ishchi muhit uchun
            creds = Credentials.from_service_account_file("credentials.json", scopes=scopes)
            logger.info("Lokal: credentials.json fayldan yuklandi.")
    except Exception as e:
        logger.error(f"Google credential yuklab bo‘lmadi: {e}")
        raise

    return creds


class GoogleSheetsDB:
    def __init__(self):
        self.sheet = None
        self.worksheet = None
        self._connect()
    
    def _connect(self):
        """Google Sheets'ga ulanish"""
        try:
            creds = get_google_credentials()
            client = gspread.authorize(creds)

            # Spreadsheetni ochish yoki yaratish
            try:
                self.sheet = client.open(SPREADSHEET_NAME)
                logger.info(f"Sheets topildi: {SPREADSHEET_NAME}")
            except gspread.SpreadsheetNotFound:
                self.sheet = client.create(SPREADSHEET_NAME)
                logger.info(f"Yangi spreadsheet yaratildi: {SPREADSHEET_NAME}")

            # Sheet2 nomli varaqni ochish yoki yaratish
            try:
                self.worksheet = self.sheet.worksheet("Sheet2")
            except gspread.WorksheetNotFound:
                self.worksheet = self.sheet.add_worksheet(
                    title="Sheet2", rows=1000, cols=10
                )
                self.worksheet.update('A1:D1', [['user_id', 'channel_id', 'title', 'date']])
                logger.info("Sheet2 yaratildi va ustunlar qo‘shildi")
            
            logger.info("Google Sheets bilan bog‘lanish muvaffaqiyatli")

        except Exception as e:
            logger.error(f"Google Sheetsga ulanib bo‘lmadi: {e}")
            raise

    def add_channel(self, user_id: int, channel_id: int, title: str) -> bool:
        """Kanalni jadvalga qo‘shish"""
        try:
            existing = self.get_channel(user_id, channel_id)
            if existing:
                return False
            date = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.worksheet.append_row([str(user_id), str(channel_id), title, date])
            logger.info(f"Kanal qo‘shildi: {title} ({channel_id}) — User: {user_id}")
            return True
        except Exception as e:
            logger.error(f"Kanal qo‘shish xatosi: {e}")
            return False

    def get_channel(self, user_id: int, channel_id: int):
        """Foydalanuvchining bitta kanalini olish"""
        try:
            records = self.worksheet.get_all_records()
            for record in records:
                if str(record.get('user_id')) == str(user_id) and \
                   str(record.get('channel_id')) == str(channel_id):
                    return record
            return None
        except Exception as e:
            logger.error(f"Kanal olish xatosi: {e}")
            return None

    def get_user_channels(self, user_id: int):
        """Foydalanuvchiga tegishli kanallarni olish"""
        try:
            records = self.worksheet.get_all_records()
            return [r for r in records if str(r.get('user_id')) == str(user_id)]
        except Exception as e:
            logger.error(f"Foydalanuvchi kanallari xatosi: {e}")
            return []

    def get_all_channels(self):
        """Admin uchun barcha kanallar"""
        try:
            return self.worksheet.get_all_records()
        except Exception as e:
            logger.error(f"Barcha kanallarni olishda xato: {e}")
            return []

    def get_stats(self):
        """Umumiy statistika"""
        try:
            records = self.worksheet.get_all_records()
            users = set(r.get('user_id') for r in records)
            return {
                'total_channels': len(records),
                'total_users': len(users),
                'channels': records
            }
        except Exception as e:
            logger.error(f"Statistika olish xatosi: {e}")
            return {'total_channels': 0, 'total_users': 0, 'channels': []}
