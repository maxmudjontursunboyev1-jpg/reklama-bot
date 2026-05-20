# 🚀 AdBot Pro - Professional Telegram Reklama Boti

## 📦 O'rnatish

```bash
# 1. Repozitoriyani yuklab oling
git clone ...
cd adbot

# 2. Virtual muhit yarating
python -m venv venv
source venv/bin/activate  # Linux/Mac
# yoki
venv\Scripts\activate  # Windows

# 3. Kutubxonalarni o'rnating
pip install -r requirements.txt

# 4. .env faylini sozlang
cp .env.example .env
nano .env  # BOT_TOKEN va ADMIN_IDS ni to'ldiring

# 5. Botni ishga tushiring
python bot.py
```

## ⚙️ Sozlash

`.env` faylini oching va to'ldiring:

```
BOT_TOKEN=BotFather dan olingan token
ADMIN_IDS=Telegram ID raqamingiz (https://t.me/userinfobot)
```

## 📋 Funksiyalar

### 📢 Reklama boshqaruvi
- Yangi reklama yaratish (matn, rasm, video, hujjat)
- HTML formatlash qo'llab-quvvatlash
- Inline tugmalar qo'shish (URL tugmalar)
- Reklama tahrirlash va o'chirish
- Status boshqaruvi (qoralama/aktiv/to'xtatilgan)

### 📡 Chat boshqaruvi
- Bot qo'shilganda avtomatik ro'yxatga olish
- Kanallar va guruhlar ro'yxati
- A'zolar sonini yangilash
- Chat aktivlashtirish/o'chirish

### 📤 Broadcast (Yuborish)
- Bir yoki ko'p chatlarga yuborish
- Progress tracking
- Muvaffaqiyat/xatolik logi

### 🕐 Scheduler (Avtomatik jadval)
- Vaqt jadvaliga muvofiq yuborish
- Takrorlanuvchi va bir martalik
- Boshlash/tugash vaqtini belgilash
- Faollashtirish/to'xtatish

### 📊 Statistika
- Umumiy bot statistikasi
- Reklama bo'yicha statistika
- So'nggi yuborish loglari

### 👥 Foydalanuvchilar
- Ro'yxat ko'rish
- Ban/unban qilish
- Ma'lumot ko'rish

## 🤖 Buyruqlar

| Buyruq | Tavsif |
|--------|--------|
| /start | Botni ishga tushirish |
| /help | Yordam |
| /ads | Reklamalar |
| /create_ad | Yangi reklama |
| /chats | Chatlar |
| /add_chat | Chat qo'shish |
| /scheduler | Jadval |
| /stats | Statistika |
| /users | Foydalanuvchilar |
| /ban <id> | Banlash |
| /unban <id> | Bandan chiqarish |
| /status | Bot holati |

## 💡 Qo'shimcha

Bot kanal/guruhga admin sifatida qo'shilishi kerak!
Admin huquqlari: Xabar yuborish, Xabarlarni ko'rish

## 📁 Fayl tuzilishi

```
adbot/
├── bot.py              # Asosiy fayl
├── config.py           # Konfiguratsiya
├── requirements.txt    # Kutubxonalar
├── .env               # Sozlamalar
├── database/
│   └── db.py          # SQLite database
├── handlers/
│   ├── admin_handlers.py
│   ├── ad_handlers.py
│   ├── broadcast_handlers.py
│   ├── chat_handlers.py
│   ├── scheduler_handlers.py
│   ├── stats_handlers.py
│   └── user_handlers.py
├── keyboards/
│   └── keyboards.py   # Barcha tugmalar
├── middlewares/
│   ├── auth_middleware.py
│   └── throttle_middleware.py
├── services/
│   └── scheduler.py   # Avtomatik yuborish
├── filters/
│   └── admin_filter.py
└── utils/
    ├── helpers.py
    └── logger.py
```
