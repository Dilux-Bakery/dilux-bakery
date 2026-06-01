"""
╔══════════════════════════════════════════╗
║      DILUX BAKERY BOT — aiogram 3.x      ║
║      Python 3.14 bilan ishlaydi          ║
╚══════════════════════════════════════════╝
Ishlatish:
  pip install aiogram
  python bot.py
"""

import os
import json
import logging
import asyncio
import base64
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
)
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, ADMIN_IDS, COURIER_IDS, MINI_APP_URL, PAYMENT_CARD, PAYMENT_NAME

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp  = Dispatcher()

# ═══════════════════════════════════════════════
#   XOTIRA
# ═══════════════════════════════════════════════
orders:      dict = {}        # {order_id: {...}}
pending_orders: dict = {}  # {user_id: order_id}
user_states: dict = {}   # {user_id: {step, order_id}}

# Buyurtmalar JSON faylga saqlanadi — bot qayta ishga tushganda yo'qolmaydi
ORDERS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orders.json")

def save_orders():
    """Buyurtmalarni diskka saqlash."""
    try:
        with open(ORDERS_FILE, "w", encoding="utf-8") as f:
            json.dump(orders, f, ensure_ascii=False, indent=2)
    except Exception as e:
        logger.error(f"Buyurtmalarni saqlashda xato: {e}")

def load_orders():
    """Buyurtmalarni diskdan o'qish (bot ishga tushganda)."""
    global orders
    if not os.path.exists(ORDERS_FILE):
        return
    try:
        with open(ORDERS_FILE, "r", encoding="utf-8") as f:
            orders = json.load(f)
        logger.info(f"📂 {len(orders)} ta buyurtma yuklandi")
    except Exception as e:
        logger.error(f"Buyurtmalarni o'qishda xato: {e}")

class Status:
    PENDING    = "pending"
    CONFIRMED  = "confirmed"
    READY      = "ready"
    ON_THE_WAY = "on_the_way"
    DELIVERED  = "delivered"
    CANCELLED  = "cancelled"

def is_admin(uid):   return uid in ADMIN_IDS
def is_courier(uid): return uid in COURIER_IDS

def order_text(o: dict) -> str:
    items = "\n".join(
        f"  {i['emoji']} {i['name']} ×{i['qty']} — {i['price'] * i['qty']:,} so'm"
        for i in o["items"]
    )
    pay_map = {"card": "💳 Karta", "click": "📱 Click", "payme": "🔵 Payme"}
    pay_txt = pay_map.get(o.get("payment", "card"), "💳 Karta")
    dtype   = "🚗 Yetkazib berish" if o.get("deliveryType") == "delivery" else "🏃 O'zi olib ketish"
    promo   = f"\n🏷 Promo: <b>{o['promo']}</b>" if o.get("promo") else ""
    fee     = o.get("deliveryFee", 0)
    if o.get("deliveryType") == "delivery":
        dtype += " — Bepul" if not fee else f" — {fee:,} so'm"
    return (
        f"📦 Buyurtma <b>{o['id']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{o['name']}</b>\n"
        f"📞 <code>{o['phone']}</code>\n"
        f"📍 {o['address']}\n"
        f"{('💬 ' + o['comment']) if o.get('comment') else ''}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{items}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Jami: {o['total']:,} so'm</b>{promo}\n"
        f"💳 {pay_txt}\n"
        f"{dtype}"
    )

# ═══════════════════════════════════════════════
#   /start
# ═══════════════════════════════════════════════
@dp.message(CommandStart())
async def cmd_start(msg: Message):
    uid  = msg.from_user.id
    args = msg.text.split()
    deep = args[1] if len(args) > 1 else None

    if deep and deep.startswith("data_"):
        # Base64 encoded order ma'lumotlari
        encoded = deep.replace("data_", "")
        try:
            # Padding tiklash
            padding = 4 - len(encoded) % 4
            if padding != 4:
                encoded += "=" * padding
            encoded = encoded.replace("-", "+").replace("_", "/")
            decoded = base64.b64decode(encoded).decode("utf-8")
            data = json.loads(decoded)
            order_id = data.get("id", f"#unknown")
            orders[order_id] = {**data, "status": Status.PENDING, "user_id": uid, "created_at": datetime.now().isoformat()}
            save_orders()
            user_states[uid] = {"step": "waiting_receipt", "order_id": order_id}
            total = data.get("total", 0)
            await msg.answer(
                f"✅ Buyurtma qabul qilindi!\n"
                f"🔖 ID: <b>{order_id}</b>\n\n"
                f"💳 <b>To'lov ma'lumotlari:</b>\n"
                f"━━━━━━━━━━━━━━━━━━\n"
                f"💳 Karta: <code>{PAYMENT_CARD}</code>\n"
                f"👤 Egasi: <b>{PAYMENT_NAME}</b>\n"
                f"💰 Summa: <b>{total:,} so'm</b>\n\n"
                f"To'lovni amalga oshirib,\n"
                f"📸 <b>Chek (skrinshot)</b> yuboring:"
            )
        except Exception as e:
            await msg.answer("❌ Ma'lumot xato keldi. Qayta urinib ko'ring.")
        return

    if deep and deep.startswith("order_"):
        order_id = "#" + deep.replace("order_", "")
        await handle_order_start(msg, order_id)
        return

    if is_admin(uid):
        await show_admin_panel(msg); return
    if is_courier(uid):
        await show_courier_panel(msg); return

    # Oddiy foydalanuvchi
    kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Buyurtma berish", web_app=WebAppInfo(url=MINI_APP_URL))],
            [KeyboardButton(text="📦 Buyurtmam")]
        ],
        resize_keyboard=True,
        persistent=True
    )
    await msg.answer(
        f"Salom, <b>{msg.from_user.first_name}</b>! 👋\n\n"
        f"<i>Dilux Bakery</i> ga xush kelibsiz 🎂\n"
        f"Buyurtma berish uchun quyidagi tugmani bosing:",
        reply_markup=kb
    )

async def handle_order_start(msg: Message, order_id: str):
    uid = msg.from_user.id
    # Order allaqachon web_app_data orqali kelgan
    if order_id in orders:
        orders[order_id]["user_id"] = uid
        user_states[uid] = {"step": "waiting_receipt", "order_id": order_id}
        o_tmp = orders.get(order_id, {})
        await msg.answer(
            f"✅ Buyurtma ID: <b>{order_id}</b>\n\n"
            f"💳 <b>To'lov ma'lumotlari:</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💳 Karta: <code>{PAYMENT_CARD}</code>\n"
            f"👤 Egasi: <b>{PAYMENT_NAME}</b>\n"
            f"💰 Summa: <b>{o_tmp.get('total',0):,} so'm</b>\n\n"
            f"To'lovni amalga oshirib,\n"
            f"📸 <b>Chek (skrinshot)</b> yuboring:"
        )
        return
    # Order hali kelmagan — pending ga qo'shamiz, web_app_data kutamiz
    pending_orders[uid] = order_id
    user_states[uid] = {"step": "waiting_receipt", "order_id": order_id}
    await msg.answer(
        f"✅ Buyurtma ID: <b>{order_id}</b>\n\n"
        f"💳 <b>To'lov ma'lumotlari:</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💳 Karta: <code>{PAYMENT_CARD}</code>\n"
        f"👤 Egasi: <b>{PAYMENT_NAME}</b>\n\n"
        f"To'lovni amalga oshirib,\n"
        f"📸 <b>Chek (skrinshot)</b> yuboring:"
    )

# ═══════════════════════════════════════════════
#   Web App data
# ═══════════════════════════════════════════════
@dp.message(F.text == "📦 Buyurtmam")
async def btn_my_order(msg: Message):
    await cmd_my_order(msg)

@dp.message(F.text == "📋 Tarix")
async def btn_tarix(msg: Message):
    await cmd_tarix(msg)

@dp.message(F.text == "📦 Buyurtmalar")
async def btn_orders(msg: Message):
    await cmd_orders(msg)

@dp.message(F.web_app_data)
async def web_app_data(msg: Message):
    uid = msg.from_user.id
    try:
        data = json.loads(msg.web_app_data.data)
    except Exception:
        await msg.answer("❌ Xatolik yuz berdi"); return

    if data.get("action") == "order_init":
        order_id = data["id"]
        # Eski state ni tozalash (3-muammo hal)
        user_states.pop(uid, None)
        orders[order_id] = {**data, "status": Status.PENDING, "user_id": uid, "created_at": datetime.now().isoformat()}
        save_orders()
        if uid in pending_orders:
            del pending_orders[uid]
        delivery_type = data.get("deliveryType", "delivery")
        user_states[uid] = {"step": "waiting_receipt", "order_id": order_id}
        total_amount = data.get("total", 0)
        await msg.answer(
            f"✅ Buyurtmangiz qabul qilindi!\n"
            f"🔖 ID: <b>{order_id}</b>\n\n"
            f"💳 <b>To'lov ma'lumotlari:</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💳 Karta: <code>{PAYMENT_CARD}</code>\n"
            f"👤 Egasi: <b>{PAYMENT_NAME}</b>\n"
            f"💰 Summa: <b>{total_amount:,} so'm</b>\n\n"
            f"To'lovni amalga oshirib,\n"
            f"📸 <b>Chek (skrinshot)</b> yuboring:"
        )

# ═══════════════════════════════════════════════
#   Rasm (chek)
# ═══════════════════════════════════════════════
@dp.message(F.photo)
async def handle_photo(msg: Message):
    uid   = msg.from_user.id
    state = user_states.get(uid)
    if not state or state.get("step") != "waiting_receipt": return

    order_id = state["order_id"]
    if order_id not in orders:
        # Buyurtma ma'lumotlari kelmagan — bo'sh chek yubormaymiz.
        # Foydalanuvchini Mini App tugmasi orqali qayta buyurtma berishga yo'naltiramiz.
        user_states.pop(uid, None)
        await msg.answer(
            "❌ Buyurtma ma'lumotlari topilmadi.\n\n"
            "Iltimos, <b>🛍 Buyurtma berish</b> tugmasi orqali\n"
            "qaytadan buyurtma bering."
        )
        return

    o = orders[order_id]
    o["receipt_file_id"] = msg.photo[-1].file_id
    save_orders()

    delivery_type = o.get("deliveryType", "delivery")
    if delivery_type == "delivery":
        user_states[uid]["step"] = "waiting_location"
        await msg.answer(
            "✅ Chek qabul qilindi!\n\n"
            "📍 Endi <b>lokatsiyangizni</b> yuboring:\n"
            "<i>📎 Qo'shimcha → Lokatsiya</i>"
        )
    else:
        # O'zi olib ketish - lokatsiya shart emas, to'g'ridan finalize
        user_states[uid]["step"] = "done"
        await finalize_order(msg, order_id)

# ═══════════════════════════════════════════════
#   Lokatsiya
# ═══════════════════════════════════════════════
@dp.message(F.location)
async def handle_location(msg: Message):
    uid   = msg.from_user.id
    state = user_states.get(uid)
    if not state or state.get("step") != "waiting_location": return

    order_id = state["order_id"]
    if order_id not in orders: return

    o = orders[order_id]
    o["location"] = {"lat": msg.location.latitude, "lon": msg.location.longitude}
    save_orders()
    user_states[uid]["step"] = "done"
    await finalize_order(msg, order_id)

# ═══════════════════════════════════════════════
#   Buyurtmani yakunlash
# ═══════════════════════════════════════════════
async def finalize_order(msg: Message, order_id: str):
    o = orders[order_id]
    uid = msg.from_user.id
    # State ni tozalash - keyingi buyurtma uchun (3-muammo hal)
    user_states.pop(uid, None)
    await msg.answer(
        f"🎉 Buyurtmangiz adminga yuborildi!\n"
        f"🔖 ID: <b>{order_id}</b>\n\n"
        f"Tez orada siz bilan bog'lanamiz ✦"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm:{order_id}"),
        InlineKeyboardButton(text="❌ Bekor",      callback_data=f"cancel:{order_id}"),
    ]])

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(
                admin_id,
                f"🔔 <b>YANGI BUYURTMA</b>\n━━━━━━━━━━━━━━━━━━\n{order_text(o)}",
                reply_markup=kb
            )
            if o.get("receipt_file_id"):
                await bot.send_photo(admin_id, o["receipt_file_id"], caption=f"📸 Chek — {order_id}")
            if o.get("location"):
                await bot.send_location(admin_id, o["location"]["lat"], o["location"]["lon"])
        except Exception as e:
            logger.error(f"Admin {admin_id}: {e}")

# ═══════════════════════════════════════════════
#   Callback — Admin tugmalari
# ═══════════════════════════════════════════════
@dp.callback_query()
async def callback_handler(cb: CallbackQuery):
    uid  = cb.from_user.id
    data = cb.data
    await cb.answer()

    # ── Tasdiqlash ──
    if data.startswith("confirm:") and is_admin(uid):
        order_id = data.split(":", 1)[1]
        o = orders.get(order_id)
        if not o: await cb.answer("Buyurtma topilmadi", show_alert=True); return
        if o["status"] != Status.PENDING: await cb.answer("Allaqachon qayta ishlangan", show_alert=True); return

        o["status"] = Status.CONFIRMED
        save_orders()
        # Admin xabariga "📦 Tayyor" tugmasi (kuryer hali yuborilmaydi)
        ready_kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text="📦 Tayyor", callback_data=f"ready:{order_id}")
        ]])
        await cb.message.edit_text(
            f"✅ <b>TASDIQLANDI</b>\n━━━━━━━━━━━━━━━━━━\n{order_text(o)}",
            reply_markup=ready_kb
        )
        # Mijozga xabar
        if o.get("user_id"):
            try:
                await bot.send_message(
                    o["user_id"],
                    f"✅ <b>Buyurtmangiz tasdiqlandi!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🔖 ID: <b>{order_id}</b>\n"
                    f"👨‍🍳 Buyurtmangiz tayyorlanmoqda...\n\n"
                    f"📊 Holat: /buyurtmam"
                )
            except: pass

    # ── Tayyor (admin bosadi) ──
    elif data.startswith("ready:") and is_admin(uid):
        order_id = data.split(":", 1)[1]
        o = orders.get(order_id)
        if not o: await cb.answer("Buyurtma topilmadi", show_alert=True); return
        if o["status"] != Status.CONFIRMED: await cb.answer("Avval tasdiqlang", show_alert=True); return

        o["status"] = Status.READY
        save_orders()
        is_delivery = o.get("deliveryType") == "delivery"

        if is_delivery:
            # Admin xabarini yangilash — endi kuryerga ketdi
            await cb.message.edit_text(
                f"📦 <b>TAYYOR — kuryerga yuborildi</b>\n━━━━━━━━━━━━━━━━━━\n{order_text(o)}"
            )
            if o.get("user_id"):
                try:
                    await bot.send_message(
                        o["user_id"],
                        f"📦 <b>Buyurtmangiz tayyor!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"🔖 ID: <b>{order_id}</b>\n"
                        f"🚗 Kuryer tez orada yo'lga chiqadi\n\n"
                        f"📊 Holat: /buyurtmam"
                    )
                except: pass
            # Kuryerlarga
            ck = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="🚗 Yo'lga chiqdim", callback_data=f"onway:{order_id}")
            ]])
            for courier_id in COURIER_IDS:
                try:
                    await bot.send_message(
                        courier_id,
                        f"🚗 <b>YANGI YETKAZISH</b>\n━━━━━━━━━━━━━━━━━━\n{order_text(o)}",
                        reply_markup=ck
                    )
                    if o.get("receipt_file_id"):
                        await bot.send_photo(
                            courier_id,
                            o["receipt_file_id"],
                            caption=f"📸 To'lov cheki — {order_id}\n👤 {o.get('name','—')}\n📞 {o.get('phone','—')}\n📍 {o.get('address','—')}"
                        )
                    if o.get("location"):
                        await bot.send_location(courier_id, o["location"]["lat"], o["location"]["lon"])
                except Exception as e:
                    logger.error(f"Kuryer {courier_id}: {e}")
        else:
            # O'zi olib ketish — kuryer yo'q. Admin "Topshirildi" tugmasi, mijozga "olib keting"
            handed_kb = InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Topshirildi", callback_data=f"handed:{order_id}")
            ]])
            await cb.message.edit_text(
                f"📦 <b>TAYYOR — olib ketishga</b>\n━━━━━━━━━━━━━━━━━━\n{order_text(o)}",
                reply_markup=handed_kb
            )
            if o.get("user_id"):
                try:
                    await bot.send_message(
                        o["user_id"],
                        f"📦 <b>Buyurtmangiz tayyor!</b>\n"
                        f"━━━━━━━━━━━━━━━━━━\n"
                        f"🔖 ID: <b>{order_id}</b>\n"
                        f"🏪 Do'kondan olib ketishingiz mumkin\n\n"
                        f"📊 Holat: /buyurtmam"
                    )
                except: pass

    # ── Topshirildi (admin, o'zi olib ketish) ──
    elif data.startswith("handed:") and is_admin(uid):
        order_id = data.split(":", 1)[1]
        o = orders.get(order_id)
        if not o: return
        o["status"] = Status.DELIVERED
        save_orders()
        await cb.message.edit_text(f"🎉 <b>TOPSHIRILDI</b> — {order_id}")
        if o.get("user_id"):
            try:
                await bot.send_message(
                    o["user_id"],
                    f"🎉 <b>Buyurtmangiz topshirildi!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🔖 ID: <b>{order_id}</b>\n"
                    f"💰 To'langan: {o.get('total',0):,} so'm\n\n"
                    f"Xarid uchun katta rahmat! ✦\n"
                    f"Dilux Bakery sizni kutadi 🎂"
                )
            except: pass

    # ── Bekor qilish ──
    elif data.startswith("cancel:") and is_admin(uid):
        order_id = data.split(":", 1)[1]
        o = orders.get(order_id)
        if not o: return
        o["status"] = Status.CANCELLED
        save_orders()
        await cb.message.edit_text(f"❌ <b>BEKOR QILINDI</b> — {order_id}")
        if o.get("user_id"):
            try:
                await bot.send_message(
                    o["user_id"],
                    f"❌ <b>Buyurtmangiz bekor qilindi</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🔖 ID: <b>{order_id}</b>\n\n"
                    f"Savollar uchun adminga murojaat qiling"
                )
            except: pass

    # ── Yo'lga chiqdim ──
    elif data.startswith("onway:") and is_courier(uid):
        order_id = data.split(":", 1)[1]
        o = orders.get(order_id)
        if not o: return
        o["status"] = Status.ON_THE_WAY
        save_orders()
        await cb.message.edit_text(
            f"🚗 <b>YO'LDA</b> — {order_id}\n{order_text(o)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Yetkazildi", callback_data=f"delivered:{order_id}")
            ]])
        )
        if o.get("user_id"):
            try:
                await bot.send_message(
                    o["user_id"],
                    f"🚗 <b>Kuryer yo'lga chiqdi!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🔖 ID: <b>{order_id}</b>\n"
                    f"📍 Manzil: {o.get('address','—')}\n"
                    f"⏱ Tez orada yetkaziladi\n\n"
                    f"📊 Holat: /buyurtmam"
                )
            except: pass
        for admin_id in ADMIN_IDS:
            try: await bot.send_message(admin_id, f"🚗 <b>{order_id}</b> — kuryer yo'lga chiqdi")
            except: pass

    # ── Yetkazildi ──
    elif data.startswith("delivered:") and is_courier(uid):
        order_id = data.split(":", 1)[1]
        o = orders.get(order_id)
        if not o: return
        o["status"] = Status.DELIVERED
        save_orders()
        await cb.message.edit_text(f"🎉 <b>YETKAZILDI</b> — {order_id}")
        if o.get("user_id"):
            try:
                await bot.send_message(
                    o["user_id"],
                    f"🎉 <b>Buyurtmangiz yetkazildi!</b>\n"
                    f"━━━━━━━━━━━━━━━━━━\n"
                    f"🔖 ID: <b>{order_id}</b>\n"
                    f"💰 To'langan: {o.get('total',0):,} so'm\n\n"
                    f"Xarid uchun katta rahmat! ✦\n"
                    f"Dilux Bakery sizni kutadi 🎂"
                )
            except: pass
        for admin_id in ADMIN_IDS:
            try: await bot.send_message(admin_id, f"🎉 <b>{order_id}</b> — yetkazildi ✅")
            except: pass

# ═══════════════════════════════════════════════
#   Admin / Kuryer panel
# ═══════════════════════════════════════════════
async def show_admin_panel(msg: Message):
    total   = len(orders)
    pending = sum(1 for o in orders.values() if o["status"] == Status.PENDING)
    revenue = sum(o["total"] for o in orders.values() if o["status"] in [Status.CONFIRMED, Status.READY, Status.ON_THE_WAY, Status.DELIVERED])
    today   = sum(1 for o in orders.values() if o.get("created_at","").startswith(datetime.now().strftime("%Y-%m-%d")))
    admin_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🛍 Mini App", web_app=WebAppInfo(url=MINI_APP_URL))],
            [KeyboardButton(text="📋 Tarix"), KeyboardButton(text="📦 Buyurtmalar")]
        ],
        resize_keyboard=True, persistent=True
    )
    await msg.answer(
        f"👨‍💼 <b>Admin Panel</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 Jami: <b>{total}</b> buyurtma\n"
        f"📅 Bugun: <b>{today}</b> ta\n"
        f"⏳ Kutilmoqda: <b>{pending}</b>\n"
        f"💰 Daromad: <b>{revenue:,} so'm</b>\n\n"
        f"📋 Tarix ko'rish: /tarix",
        reply_markup=admin_kb
    )

async def show_courier_panel(msg: Message):
    active_orders = [o for o in orders.values()
        if o["status"] in [Status.READY, Status.ON_THE_WAY]
        and o.get("deliveryType") == "delivery"]
    delivered_today = sum(1 for o in orders.values()
        if o["status"] == Status.DELIVERED
        and o.get("created_at","").startswith(datetime.now().strftime("%Y-%m-%d")))

    courier_kb = ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="🗺 Faol buyurtmalar")],
            [KeyboardButton(text="📋 Tarix"), KeyboardButton(text="📦 Buyurtmam")]
        ],
        resize_keyboard=True, persistent=True
    )
    await msg.answer(
        f"🚗 <b>Kuryer Panel</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 Faol yetkazishlar: <b>{len(active_orders)}</b>\n"
        f"🎉 Bugun yetkazildi: <b>{delivered_today}</b>\n\n"
        f"🗺 Faol buyurtmalar: /faol\n"
        f"📋 Tarix: /tarix",
        reply_markup=courier_kb
    )

@dp.message(Command("faol"))
@dp.message(F.text == "🗺 Faol buyurtmalar")
async def cmd_active_orders(msg: Message):
    uid = msg.from_user.id
    if not (is_admin(uid) or is_courier(uid)):
        await msg.answer("⛔ Ruxsat yo'q"); return

    active = [o for o in orders.values()
        if o["status"] in [Status.READY, Status.ON_THE_WAY]
        and o.get("deliveryType") == "delivery"]
    if not active:
        await msg.answer(
            "📭 <b>Hozircha faol buyurtma yo'q</b>\n\n"
            "Yangi buyurtma kelganda sizga xabar yuboriladi!"
        )
        return

    await msg.answer(
        f"🗺 <b>Faol buyurtmalar</b> — {len(active)} ta\n"
        f"━━━━━━━━━━━━━━━━━━"
    )
    for o in active:
        status_map = {Status.READY: "📦 Tayyor", Status.ON_THE_WAY: "🚗 Yo'lda"}
        status_label = status_map.get(o["status"], o["status"])
        items_text = "\n".join(f"  {i['emoji']} {i['name']} ×{i['qty']}" for i in o.get("items", []))

        # Buyurtma xabari
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text="🚗 Yo'lga chiqdim" if o["status"] == Status.READY else "✅ Yetkazildi",
                callback_data=f"{'onway' if o['status'] == Status.READY else 'delivered'}:{o['id']}"
            )
        ]])
        text = (
            f"{status_label} | <b>{o['id']}</b>\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"👤 {o.get('name','—')}\n"
            f"📞 <code>{o.get('phone','—')}</code>\n"
            f"📍 <b>{o.get('address','—')}</b>\n"
            f"{'💬 ' + o['comment'] if o.get('comment') else ''}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"{items_text}\n"
            f"━━━━━━━━━━━━━━━━━━\n"
            f"💰 <b>{o.get('total',0):,} so'm</b>"
        )
        await msg.answer(text, reply_markup=kb)

        # Lokatsiyani alohida yuborish
        if o.get("location"):
            await msg.answer_location(
                latitude=o["location"]["lat"],
                longitude=o["location"]["lon"]
            )

@dp.message(Command("buyurtmam"))
async def cmd_my_order(msg: Message):
    uid = msg.from_user.id
    # Foydalanuvchining oxirgi buyurtmasini topish
    user_orders = [o for o in orders.values() if o.get("user_id") == uid]
    if not user_orders:
        await msg.answer(
            "📭 Sizda hali buyurtma yo'q\n\n"
            "Buyurtma berish uchun 👇\n"
            "<b>Buyurtma berish</b> tugmasini bosing!"
        )
        return
    # Oxirgi buyurtma
    last = sorted(user_orders, key=lambda x: x.get("id",""), reverse=True)[0]
    status_map = {
        "pending":    ("⏳", "Tekshirilmoqda",     "Adminimiz tez orada ko'rib chiqadi"),
        "confirmed":  ("✅", "Tasdiqlandi",         "Buyurtmangiz tayyorlanmoqda"),
        "ready":      ("📦", "Tayyor",              "Buyurtmangiz tayyor bo'ldi!"),
        "on_the_way": ("🚗", "Kuryer yo'lda",       "Tez orada yetkaziladi!"),
        "delivered":  ("🎉", "Yetkazildi",          "Xarid uchun rahmat! ✦"),
        "cancelled":  ("❌", "Bekor qilindi",       "Savollar uchun adminga murojaat qiling"),
    }
    emoji, label, desc = status_map.get(last["status"], ("❓", "Noma'lum", ""))
    items_text = "\n".join(
        f"  {i['emoji']} {i['name']} ×{i['qty']}"
        for i in last.get("items", [])
    ) or "  —"
    await msg.answer(
        f"{emoji} <b>Buyurtma holati</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🔖 ID: <b>{last['id']}</b>\n"
        f"📊 Holat: <b>{label}</b>\n"
        f"💬 {desc}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🛍 Mahsulotlar:\n{items_text}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 Jami: <b>{last.get('total',0):,} so'm</b>"
    )

@dp.message(Command("orders"))
async def cmd_orders(msg: Message):
    if not is_admin(msg.from_user.id):
        await msg.answer("⛔ Ruxsat yo'q"); return
    if not orders:
        await msg.answer("📭 Hali buyurtma yo'q"); return
    status_emoji = {Status.PENDING:"⏳", Status.CONFIRMED:"✅", Status.READY:"📦", Status.ON_THE_WAY:"🚗", Status.DELIVERED:"🎉", Status.CANCELLED:"❌"}
    text = "<b>Oxirgi buyurtmalar:</b>\n━━━━━━━━━━━━━━━━━━\n"
    for o in list(orders.values())[-10:]:
        text += f"{status_emoji.get(o['status'],'❓')} <b>{o['id']}</b> — {o['name']} — {o['total']:,} so'm\n"
    await msg.answer(text)

# ═══════════════════════════════════════════════
#   MAIN
# ═══════════════════════════════════════════════
# ═══════════════════════════════════════════════
#   TARIX — /tarix buyrug'i
# ═══════════════════════════════════════════════

def get_period_label(period: str) -> str:
    return {"today": "📅 Bugun", "week": "📆 Hafta", "month": "🗓 Oy", "all": "📋 Hammasi"}.get(period, "📋")

def get_status_label(status: str) -> str:
    return {
        "pending":    "⏳ Kutilmoqda",
        "confirmed":  "✅ Tasdiqlangan",
        "ready":      "📦 Tayyor",
        "on_the_way": "🚗 Yo'lda",
        "delivered":  "🎉 Yetkazildi",
        "cancelled":  "❌ Bekor",
        "all":        "📋 Barchasi",
    }.get(status, status)

def filter_orders_by_period(period: str) -> list:
    now = datetime.now()
    result = []
    for o in orders.values():
        order_time = o.get("created_at")
        if not order_time:
            if period == "all":
                result.append(o)
            continue
        try:
            dt = datetime.fromisoformat(order_time)
        except:
            result.append(o) if period == "all" else None
            continue
        if period == "today" and dt.date() == now.date():
            result.append(o)
        elif period == "week" and dt >= now - timedelta(days=7):
            result.append(o)
        elif period == "month" and dt >= now - timedelta(days=30):
            result.append(o)
        elif period == "all":
            result.append(o)
    return result

def filter_by_status(order_list: list, status: str) -> list:
    if status == "all":
        return order_list
    return [o for o in order_list if o.get("status") == status]

def build_history_text(order_list: list, period: str, status: str, page: int = 0) -> tuple:
    """Buyurtmalar ro'yxatini formatlash. (text, total_pages)"""
    PAGE_SIZE = 5
    filtered = filter_by_status(order_list, status)
    total = len(filtered)
    total_pages = max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE)
    page = max(0, min(page, total_pages - 1))
    start = page * PAGE_SIZE
    chunk = list(reversed(filtered))[start:start + PAGE_SIZE]

    status_emoji = {
        "pending": "⏳", "confirmed": "✅", "ready": "📦",
        "on_the_way": "🚗", "delivered": "🎉", "cancelled": "❌"
    }
    period_label = get_period_label(period)
    status_label = get_status_label(status)

    # Revenue
    revenue = sum(o.get("total", 0) for o in filtered if o.get("status") in ["delivered", "confirmed", "ready", "on_the_way"])

    text = (
        f"📊 <b>Buyurtmalar tarixi</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"🗓 Davr: {period_label} | {status_label}\n"
        f"📦 Jami: <b>{total}</b> ta | 💰 <b>{revenue:,} so'm</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
    )
    if not chunk:
        text += "\n📭 Bu davrda buyurtma yo'q"
    else:
        for o in chunk:
            e = status_emoji.get(o.get("status", ""), "❓")
            items_short = ", ".join(f"{i['emoji']}{i['name'][:8]}" for i in o.get("items", [])[:2])
            if len(o.get("items", [])) > 2:
                items_short += "..."
            text += (
                f"\n{e} <b>{o['id']}</b> — {o.get('name','—')}\n"
                f"   📞 {o.get('phone','—')} | 💰 {o.get('total',0):,} so'm\n"
                f"   🛍 {items_short or '—'}\n"
                f"   🕐 {o.get('time','—')}\n"
            )
    if total_pages > 1:
        text += f"\n━━━━━━━━━━━━━━━━━━\n📄 Sahifa {page+1}/{total_pages}"
    return text, total_pages, page

def build_history_kb(period: str, status: str, page: int, total_pages: int) -> InlineKeyboardMarkup:
    """Tarix tugmalari"""
    # Period tugmalari
    periods = [("📅 Bugun","today"),("📆 Hafta","week"),("🗓 Oy","month"),("📋 Hammasi","all")]
    row1 = [
        InlineKeyboardButton(
            text=f"{'›' if p==period else ''}{label}{'‹' if p==period else ''}",
            callback_data=f"hist_p:{p}:{status}:0"
        ) for label, p in periods
    ]
    # Status tugmalari
    statuses = [("⏳","pending"),("✅","confirmed"),("📦","ready"),("🚗","on_the_way"),("🎉","delivered"),("❌","cancelled"),("📋","all")]
    row2 = [
        InlineKeyboardButton(
            text=f"[{e}]" if s==status else e,
            callback_data=f"hist_s:{period}:{s}:0"
        ) for e, s in statuses
    ]
    # Sahifa tugmalari
    row3 = []
    if total_pages > 1:
        if page > 0:
            row3.append(InlineKeyboardButton(text="⬅️", callback_data=f"hist_pg:{period}:{status}:{page-1}"))
        row3.append(InlineKeyboardButton(text=f"{page+1}/{total_pages}", callback_data="hist_noop"))
        if page < total_pages - 1:
            row3.append(InlineKeyboardButton(text="➡️", callback_data=f"hist_pg:{period}:{status}:{page+1}"))

    rows = [row1, row2]
    if row3:
        rows.append(row3)
    return InlineKeyboardMarkup(inline_keyboard=rows)

@dp.message(Command("tarix"))
async def cmd_tarix(msg: Message):
    uid = msg.from_user.id
    if not (is_admin(uid) or is_courier(uid)):
        await msg.answer("⛔ Ruxsat yo'q"); return
    period, status = "today", "all"
    order_list = filter_orders_by_period(period)
    text, total_pages, page = build_history_text(order_list, period, status, 0)
    kb = build_history_kb(period, status, 0, total_pages)
    await msg.answer(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("hist_"))
async def history_callback(cb: CallbackQuery):
    uid = cb.from_user.id
    if not (is_admin(uid) or is_courier(uid)):
        await cb.answer("⛔ Ruxsat yo'q", show_alert=True); return
    await cb.answer()
    parts = cb.data.split(":")
    action = parts[0]
    if action == "hist_noop":
        return
    period = parts[1]
    status = parts[2]
    page   = int(parts[3]) if len(parts) > 3 else 0
    order_list = filter_orders_by_period(period)
    text, total_pages, page = build_history_text(order_list, period, status, page)
    kb = build_history_kb(period, status, page, total_pages)
    try:
        await cb.message.edit_text(text, reply_markup=kb)
    except: pass

async def main():
    load_orders()
    logger.info("🍰 Dilux Bakery Bot ishga tushdi!")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
