# ════════════════════════════════════════
#   config.example.py — GitHub uchun shablon
#   Bu faylni nusxalab config.py yarating
#   va o'z ma'lumotlaringizni kiriting
# ════════════════════════════════════════

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"       # @BotFather dan

ADMIN_IDS = [
    123456789,    # Admin Telegram ID (@userinfobot dan oling)
]

COURIER_IDS = [
    987654321,    # Kuryer Telegram ID
]

MINI_APP_URL = "https://your-app.vercel.app"

PAYMENT_CARD = "8600 XXXX XXXX XXXX"
PAYMENT_NAME = "Dilux Bakery"

# ── Google Sheets integratsiyasi (ixtiyoriy) ──
# 1) Google Sheet yarating, SA email ga "Editor" qilib ulashing
# 2) URL dan ID ni oling: docs.google.com/spreadsheets/d/<SHEET_ID>/edit
SHEET_ID = ""                              # bo'sh bo'lsa Sheets o'chiq
SERVICE_ACCOUNT_FILE = "service_account.json"
