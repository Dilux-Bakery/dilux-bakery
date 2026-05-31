"""
╔══════════════════════════════════════════╗
║      DILUX BAKERY BOT — aiogram 3.x      ║
║      Python 3.14 bilan ishlaydi          ║
╚══════════════════════════════════════════╝
Ishlatish:
  pip install aiogram
  python bot.py
"""

import json
import logging
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
    ReplyKeyboardMarkup, KeyboardButton, WebAppInfo,
)
from aiogram.filters import CommandStart, Command
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from config import BOT_TOKEN, ADMIN_IDS, COURIER_IDS, MINI_APP_URL

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

class Status:
    PENDING    = "pending"
    CONFIRMED  = "confirmed"
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
        keyboard=[[KeyboardButton(text="🛍 Buyurtma berish", web_app=WebAppInfo(url=MINI_APP_URL))]],
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
        await msg.answer(
            f"✅ Buyurtma ID: <b>{order_id}</b>\n\n"
            f"📸 <b>To'lov chekingizni</b> (skrinshot) yuboring:"
        )
        return
    # Order hali kelmagan — pending ga qo'shamiz, web_app_data kutamiz
    pending_orders[uid] = order_id
    user_states[uid] = {"step": "waiting_receipt", "order_id": order_id}
    await msg.answer(
        f"✅ Buyurtma ID: <b>{order_id}</b>\n\n"
        f"📸 <b>To'lov chekingizni</b> (skrinshot) yuboring:"
    )

# ═══════════════════════════════════════════════
#   Web App data
# ═══════════════════════════════════════════════
@dp.message(F.web_app_data)
async def web_app_data(msg: Message):
    uid = msg.from_user.id
    try:
        data = json.loads(msg.web_app_data.data)
    except Exception:
        await msg.answer("❌ Xatolik yuz berdi"); return

    if data.get("action") == "order_init":
        order_id = data["id"]
        orders[order_id] = {**data, "status": Status.PENDING, "user_id": uid}
        # Agar foydalanuvchi oldin deep link orqali kelgan bo'lsa
        if uid in pending_orders:
            del pending_orders[uid]
        user_states[uid] = {"step": "waiting_receipt", "order_id": order_id}
        await msg.answer(
            f"✅ Buyurtmangiz qabul qilindi!\n"
            f"🔖 ID: <b>{order_id}</b>\n\n"
            f"📸 Endi <b>to'lov cheki</b> (skrinshot) yuboring:"
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
        # Pending order bo'lsa — minimal order yaratamiz
        if uid in pending_orders or True:
            orders[order_id] = {
                "id": order_id, "status": Status.PENDING, "user_id": uid,
                "name": msg.from_user.full_name,
                "phone": "—", "address": "—", "comment": "",
                "deliveryType": "delivery", "payment": "card",
                "promo": None, "items": [], "total": 0,
                "time": "—"
            }
        else:
            await msg.answer("❌ Buyurtma topilmadi. /start bosing"); return

    o = orders[order_id]
    o["receipt_file_id"] = msg.photo[-1].file_id

    if o.get("deliveryType") == "delivery":
        user_states[uid]["step"] = "waiting_location"
        await msg.answer(
            "✅ Chek qabul qilindi!\n\n"
            "📍 Endi <b>lokatsiyangizni</b> yuboring:\n"
            "<i>📎 Qo'shimcha → Lokatsiya</i>"
        )
    else:
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
    user_states[uid]["step"] = "done"
    await finalize_order(msg, order_id)

# ═══════════════════════════════════════════════
#   Buyurtmani yakunlash
# ═══════════════════════════════════════════════
async def finalize_order(msg: Message, order_id: str):
    o = orders[order_id]
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
        await cb.message.edit_text(
            f"✅ <b>TASDIQLANDI</b>\n━━━━━━━━━━━━━━━━━━\n{order_text(o)}"
        )
        # Mijozga xabar
        if o.get("user_id"):
            try:
                await bot.send_message(o["user_id"],
                    f"✅ Buyurtmangiz <b>{order_id}</b> tasdiqlandi!\nTez orada yetkaziladi 🚗")
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
                    await bot.send_photo(courier_id, o["receipt_file_id"], caption=f"📸 Chek — {order_id}")
                if o.get("location"):
                    await bot.send_location(courier_id, o["location"]["lat"], o["location"]["lon"])
            except Exception as e:
                logger.error(f"Kuryer {courier_id}: {e}")

    # ── Bekor qilish ──
    elif data.startswith("cancel:") and is_admin(uid):
        order_id = data.split(":", 1)[1]
        o = orders.get(order_id)
        if not o: return
        o["status"] = Status.CANCELLED
        await cb.message.edit_text(f"❌ <b>BEKOR QILINDI</b> — {order_id}")
        if o.get("user_id"):
            try:
                await bot.send_message(o["user_id"],
                    f"❌ Buyurtmangiz <b>{order_id}</b> bekor qilindi.\nSavollar: @dilux_admin")
            except: pass

    # ── Yo'lga chiqdim ──
    elif data.startswith("onway:") and is_courier(uid):
        order_id = data.split(":", 1)[1]
        o = orders.get(order_id)
        if not o: return
        o["status"] = Status.ON_THE_WAY
        await cb.message.edit_text(
            f"🚗 <b>YO'LDA</b> — {order_id}\n{order_text(o)}",
            reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
                InlineKeyboardButton(text="✅ Yetkazildi", callback_data=f"delivered:{order_id}")
            ]])
        )
        if o.get("user_id"):
            try: await bot.send_message(o["user_id"], f"🚗 Kuryer yo'lda! Buyurtma: <b>{order_id}</b>")
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
        await cb.message.edit_text(f"🎉 <b>YETKAZILDI</b> — {order_id}")
        if o.get("user_id"):
            try: await bot.send_message(o["user_id"],
                f"🎉 Buyurtmangiz <b>{order_id}</b> yetkazildi!\nRahmat! ✦ Dilux Bakery")
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
    revenue = sum(o["total"] for o in orders.values() if o["status"] in [Status.CONFIRMED, Status.ON_THE_WAY, Status.DELIVERED])
    await msg.answer(
        f"👨‍💼 <b>Admin Panel</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 Jami: <b>{total}</b> buyurtma\n"
        f"⏳ Kutilmoqda: <b>{pending}</b>\n"
        f"💰 Daromad: <b>{revenue:,} so'm</b>"
    )

async def show_courier_panel(msg: Message):
    active = sum(1 for o in orders.values() if o["status"] in [Status.CONFIRMED, Status.ON_THE_WAY])
    await msg.answer(
        f"🚗 <b>Kuryer Panel</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 Faol yetkazishlar: <b>{active}</b>"
    )

@dp.message(Command("orders"))
async def cmd_orders(msg: Message):
    if not is_admin(msg.from_user.id):
        await msg.answer("⛔ Ruxsat yo'q"); return
    if not orders:
        await msg.answer("📭 Hali buyurtma yo'q"); return
    status_emoji = {Status.PENDING:"⏳", Status.CONFIRMED:"✅", Status.ON_THE_WAY:"🚗", Status.DELIVERED:"🎉", Status.CANCELLED:"❌"}
    text = "<b>Oxirgi buyurtmalar:</b>\n━━━━━━━━━━━━━━━━━━\n"
    for o in list(orders.values())[-10:]:
        text += f"{status_emoji.get(o['status'],'❓')} <b>{o['id']}</b> — {o['name']} — {o['total']:,} so'm\n"
    await msg.answer(text)

# ═══════════════════════════════════════════════
#   MAIN
# ═══════════════════════════════════════════════
async def main():
    logger.info("🍰 Dilux Bakery Bot ishga tushdi!")
    await dp.start_polling(bot, drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
