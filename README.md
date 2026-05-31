# Dilux Bakery Bot — Ishga tushirish

## 1. O'rnatish
```bash
pip install -r requirements.txt
```

## 2. config.py ni to'ldirish
```python
BOT_TOKEN   = "1234567890:ABC..."   # @BotFather dan
ADMIN_IDS   = [123456789]           # @userinfobot dan oling
COURIER_IDS = [987654321]
MINI_APP_URL = "https://sizning-sayt.vercel.app"
```

## 3. Mini App ichida BOT_USERNAME ni o'zgartiring
dilux-bakery-v3.html ichida:
```js
const BOT_USERNAME = 'SizningBotUsername';  // @ belgisisiz
```

## 4. Ishga tushirish
```bash
python bot.py
```

---

## Jarayon

```
Mijoz → Mini App'da buyurtma beradi
  ↓
Bot → Mijozga: "Chek yuboring"
  ↓
Mijoz → 📸 Chek yuboradi
  ↓  (faqat yetkazishda)
Mijoz → 📍 Lokatsiya yuboradi
  ↓
Bot → Adminga: Buyurtma + Chek + Lokatsiya  [✅ Tasdiqlash] [❌ Bekor]
  ↓
Admin → ✅ bosadi
  ↓
Bot → Kuryerga: Buyurtma + Chek + Lokatsiya  [🚗 Yo'lga chiqdim]
  ↓
Kuryer → 🚗 bosadi → Mijozga xabar
  ↓
Kuryer → ✅ Yetkazildi → Barcha xabardor qilinadi
```

## Buyruqlar
- `/start` — Botni boshlash
- `/orders` — Admin: oxirgi buyurtmalar (faqat adminlar)

## ID larni topish
Telegram'da @userinfobot ga /start yozing — u sizning ID ngizni beradi.
