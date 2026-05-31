"""
╔══════════════════════════════════════════╗
║      DILUX BAKERY BOT — bot.py           ║
║  python-telegram-bot v20+                ║
╚══════════════════════════════════════════╝

Ishlatish:
  pip install python-telegram-bot
  python bot.py
"""

import json
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, KeyboardButton, WebAppInfo
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    CallbackQueryHandler, ContextTypes, filters
)
from config import BOT_TOKEN, ADMIN_IDS, COURIER_IDS, MINI_APP_URL, PAYMENT_CARD, PAYMENT_NAME

logging.basicConfig(
    format="%(asctime)s | %(levelname)s | %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════
#   XOTIRA (oddiy dict — production'da DB kerak)
# ═══════════════════════════════════════════════
# {order_id: {order_data, status, user_id, ...}}
orders: dict = {}

# Foydalanuvchi holati: {user_id: {step, order_id}}
user_states: dict = {}

# Buyurtma holatlari
class Status:
    PENDING    = "pending"      # Chek/lokatsiya kutilmoqda
    CONFIRMED  = "confirmed"    # Admin tasdiqladi
    ON_THE_WAY = "on_the_way"   # Kuryer yo'lda
    DELIVERED  = "delivered"    # Yetkazildi
    CANCELLED  = "cancelled"    # Bekor qilindi

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def is_courier(user_id: int) -> bool:
    return user_id in COURIER_IDS

def order_text(o: dict, for_role="admin") -> str:
    """Buyurtma matnini formatlash"""
    items = "\n".join(
        f"  {i['emoji']} {i['name']} ×{i['qty']} — {i['price'] * i['qty']:,} so'm"
        for i in o["items"]
    )
    pay_map = {"card": "💳 Karta", "click": "📱 Click", "payme": "🔵 Payme"}
    pay_txt = pay_map.get(o.get("payment", "card"), "💳 Karta")
    dtype   = "🚗 Yetkazib berish" if o.get("deliveryType") == "delivery" else "🏃 O'zi olib ketish"
    promo   = f"\n🏷 Promo: <b>{o['promo']}</b>" if o.get("promo") else ""

    base = (
        f"📦 Buyurtma <b>{o['id']}</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"👤 <b>{o['name']}</b>\n"
        f"📞 <code>{o['phone']}</code>\n"
        f"📍 {o['address']}\n"
        f"{f'💬 {o[\"comment\"]}' if o.get('comment') else ''}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"{items}\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"💰 <b>Jami: {o['total']:,} so'm</b>{promo}\n"
        f"💳 {pay_txt}\n"
        f"{dtype}"
    )
    return base

# ═══════════════════════════════════════════════
#   /start
# ═══════════════════════════════════════════════
async def cmd_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uid  = user.id
    args = ctx.args  # /start order_1001 bo'lsa ['order_1001']

    # Mini App'dan yo'naltirilgan — order ID bor
    if args and args[0].startswith("order_"):
        raw_id = args[0].replace("order_", "#")
        await handle_order_start(update, ctx, raw_id)
        return

    # Admin yoki kuryer bo'lsa panel ko'rsatish
    if is_admin(uid):
        await show_admin_panel(update, ctx)
        return
    if is_courier(uid):
        await show_courier_panel(update, ctx)
        return

    # Oddiy foydalanuvchi — pastki doimiy Web App tugmasi
    web_kb = ReplyKeyboardMarkup(
        [[KeyboardButton("🛍 Buyurtma berish", web_app=WebAppInfo(url=MINI_APP_URL))]],
        resize_keyboard=True,
        persistent=True
    )
    await update.message.reply_text(
        f"Salom, <b>{user.first_name}</b>! 👋\n\n"
        f"<i>Dilux Bakery</i> ga xush kelibsiz 🎂\n"
        f"Buyurtma berish uchun quyidagi tugmani bosing:",
        parse_mode="HTML",
        reply_markup=web_kb
    )

async def handle_order_start(update: Update, ctx: ContextTypes.DEFAULT_TYPE, order_id: str):
    """Mini App'dan kelgan foydalanuvchini qabul qilish"""
    uid = update.effective_user.id

    # Agar buyurtma allaqachon mavjud bo'lsa
    if order_id in orders:
        o = orders[order_id]
        await update.message.reply_text(
            f"✅ Buyurtmangiz <b>{order_id}</b> allaqachon qabul qilingan!\n"
            f"Holat: <b>{o['status']}</b>",
            parse_mode="HTML"
        )
        return

    # Foydalanuvchi ID ni saqlash (keyinroq chek va lokatsiya kelganda kerak)
    user_states[uid] = {"step": "waiting_order_id", "order_id": order_id}

    await update.message.reply_text(
        f"✅ Buyurtma ID: <b>{order_id}</b>\n\n"
        f"Iltimos, keyingi qadam sifatida:\n"
        f"📸 <b>To'lov chekingizni</b> (skrinshot) yuboring",
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════════
#   Web App orqali kelgan ma'lumot
# ═══════════════════════════════════════════════
async def web_app_data(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    try:
        data = json.loads(update.message.web_app_data.data)
    except Exception:
        await update.message.reply_text("❌ Xatolik yuz berdi")
        return

    if data.get("action") == "order_init":
        order_id = data["id"]
        orders[order_id] = {**data, "status": Status.PENDING, "user_id": uid}
        user_states[uid]  = {"step": "waiting_receipt", "order_id": order_id}

        await update.message.reply_text(
            f"✅ Buyurtmangiz qabul qilindi!\n"
            f"🔖 ID: <b>{order_id}</b>\n\n"
            f"📸 Endi <b>to'lov cheki</b> (skrinshot) yuboring:",
            parse_mode="HTML"
        )

# ═══════════════════════════════════════════════
#   Rasm (chek screenshoti)
# ═══════════════════════════════════════════════
async def handle_photo(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    state = user_states.get(uid)

    if not state or state.get("step") != "waiting_receipt":
        return

    order_id = state["order_id"]
    if order_id not in orders:
        await update.message.reply_text("❌ Buyurtma topilmadi. /start bosing")
        return

    o = orders[order_id]

    # Chekni saqlash
    photo_id = update.message.photo[-1].file_id
    o["receipt_file_id"] = photo_id

    # Yetkazib berish turini tekshirish
    if o.get("deliveryType") == "delivery":
        user_states[uid]["step"] = "waiting_location"
        await update.message.reply_text(
            "✅ Chek qabul qilindi!\n\n"
            "📍 Endi <b>lokatsiyangizni</b> yuboring:\n"
            "<i>📎 Qo'shimcha → Lokatsiya</i>",
            parse_mode="HTML"
        )
    else:
        # O'zi olib ketish — lokatsiya shart emas
        user_states[uid]["step"] = "done"
        await finalize_order(update, ctx, order_id)

# ═══════════════════════════════════════════════
#   Lokatsiya
# ═══════════════════════════════════════════════
async def handle_location(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid   = update.effective_user.id
    state = user_states.get(uid)

    if not state or state.get("step") != "waiting_location":
        return

    order_id = state["order_id"]
    if order_id not in orders:
        return

    o = orders[order_id]
    loc = update.message.location
    o["location"] = {"lat": loc.latitude, "lon": loc.longitude}
    user_states[uid]["step"] = "done"

    await finalize_order(update, ctx, order_id)

# ═══════════════════════════════════════════════
#   Buyurtmani yakunlash — admin + kuryerga yuborish
# ═══════════════════════════════════════════════
async def finalize_order(update: Update, ctx: ContextTypes.DEFAULT_TYPE, order_id: str):
    o   = orders[order_id]
    uid = update.effective_user.id

    # Mijozga tasdiqlash xabari
    await update.message.reply_text(
        f"🎉 Buyurtmangiz adminga yuborildi!\n"
        f"🔖 ID: <b>{order_id}</b>\n\n"
        f"Tez orada siz bilan bog'lanamiz ✦",
        parse_mode="HTML"
    )

    # Admin tugmalari
    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm:{order_id}"),
            InlineKeyboardButton("❌ Bekor", callback_data=f"cancel:{order_id}"),
        ]
    ])

    order_msg = order_text(o)

    # Har bir adminga yuborish
    for admin_id in ADMIN_IDS:
        try:
            # Matn xabari
            sent = await ctx.bot.send_message(
                chat_id=admin_id,
                text=f"🔔 <b>YANGI BUYURTMA</b>\n━━━━━━━━━━━━━━━━━━\n{order_msg}",
                parse_mode="HTML",
                reply_markup=kb
            )
            o.setdefault("admin_msgs", []).append({"chat_id": admin_id, "message_id": sent.message_id})

            # Chek rasmini yuborish
            if o.get("receipt_file_id"):
                await ctx.bot.send_photo(
                    chat_id=admin_id,
                    photo=o["receipt_file_id"],
                    caption=f"📸 To'lov cheki — {order_id}"
                )

            # Lokatsiyani yuborish
            if o.get("location"):
                await ctx.bot.send_location(
                    chat_id=admin_id,
                    latitude=o["location"]["lat"],
                    longitude=o["location"]["lon"]
                )
        except Exception as e:
            logger.error(f"Admin {admin_id} ga yuborishda xato: {e}")

# ═══════════════════════════════════════════════
#   Callback — Admin tugmalari
# ═══════════════════════════════════════════════
async def callback_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    query  = update.callback_query
    uid    = query.from_user.id
    data   = query.data
    await query.answer()

    # ── Admin: tasdiqlash ──
    if data.startswith("confirm:") and is_admin(uid):
        order_id = data.split(":", 1)[1]
        o = orders.get(order_id)
        if not o:
            await query.edit_message_text("❌ Buyurtma topilmadi"); return
        if o["status"] != Status.PENDING:
            await query.answer("Bu buyurtma allaqachon qayta ishlangan", show_alert=True); return

        o["status"] = Status.CONFIRMED

        # Admin xabarini yangilash
        await query.edit_message_text(
            f"✅ <b>TASDIQLANDI</b>\n━━━━━━━━━━━━━━━━━━\n{order_text(o)}",
            parse_mode="HTML"
        )

        # Mijozga xabar
        if o.get("user_id"):
            try:
                await ctx.bot.send_message(
                    chat_id=o["user_id"],
                    text=f"✅ Buyurtmangiz <b>{order_id}</b> tasdiqlandi!\n"
                         f"Tez orada yetkaziladi 🚗",
                    parse_mode="HTML"
                )
            except: pass

        # Kuryerlarga yuborish
        courier_kb = InlineKeyboardMarkup([[
            InlineKeyboardButton("🚗 Yo'lga chiqdim", callback_data=f"onway:{order_id}")
        ]])
        for courier_id in COURIER_IDS:
            try:
                await ctx.bot.send_message(
                    chat_id=courier_id,
                    text=f"🚗 <b>YANGI YETKAZISH</b>\n━━━━━━━━━━━━━━━━━━\n{order_text(o, 'courier')}",
                    parse_mode="HTML",
                    reply_markup=courier_kb
                )
                if o.get("receipt_file_id"):
                    await ctx.bot.send_photo(
                        chat_id=courier_id,
                        photo=o["receipt_file_id"],
                        caption=f"📸 To'lov cheki — {order_id}"
                    )
                if o.get("location"):
                    await ctx.bot.send_location(
                        chat_id=courier_id,
                        latitude=o["location"]["lat"],
                        longitude=o["location"]["lon"]
                    )
            except Exception as e:
                logger.error(f"Kuryer {courier_id} ga yuborishda xato: {e}")

    # ── Admin: bekor qilish ──
    elif data.startswith("cancel:") and is_admin(uid):
        order_id = data.split(":", 1)[1]
        o = orders.get(order_id)
        if not o: return
        o["status"] = Status.CANCELLED
        await query.edit_message_text(
            f"❌ <b>BEKOR QILINDI</b> — {order_id}",
            parse_mode="HTML"
        )
        if o.get("user_id"):
            try:
                await ctx.bot.send_message(
                    chat_id=o["user_id"],
                    text=f"❌ Buyurtmangiz <b>{order_id}</b> bekor qilindi.\n"
                         f"Savollar uchun: @dilux_admin",
                    parse_mode="HTML"
                )
            except: pass

    # ── Kuryer: yo'lga chiqdim ──
    elif data.startswith("onway:") and is_courier(uid):
        order_id = data.split(":", 1)[1]
        o = orders.get(order_id)
        if not o: return
        o["status"] = Status.ON_THE_WAY

        await query.edit_message_text(
            f"🚗 <b>YO'LDA</b> — {order_id}\n{order_text(o, 'courier')}",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([[
                InlineKeyboardButton("✅ Yetkazildi", callback_data=f"delivered:{order_id}")
            ]])
        )
        # Mijoz va adminga xabar
        if o.get("user_id"):
            try:
                await ctx.bot.send_message(
                    chat_id=o["user_id"],
                    text=f"🚗 Kuryer yo'lda! Buyurtma: <b>{order_id}</b>",
                    parse_mode="HTML"
                )
            except: pass
        for admin_id in ADMIN_IDS:
            try:
                await ctx.bot.send_message(
                    chat_id=admin_id,
                    text=f"🚗 <b>{order_id}</b> — kuryer yo'lga chiqdi",
                    parse_mode="HTML"
                )
            except: pass

    # ── Kuryer: yetkazildi ──
    elif data.startswith("delivered:") and is_courier(uid):
        order_id = data.split(":", 1)[1]
        o = orders.get(order_id)
        if not o: return
        o["status"] = Status.DELIVERED

        await query.edit_message_text(
            f"✅ <b>YETKAZILDI</b> — {order_id}",
            parse_mode="HTML"
        )
        if o.get("user_id"):
            try:
                await ctx.bot.send_message(
                    chat_id=o["user_id"],
                    text=f"🎉 Buyurtmangiz <b>{order_id}</b> yetkazildi!\n"
                         f"Xarid uchun rahmat! ✦ Dilux Bakery",
                    parse_mode="HTML"
                )
            except: pass
        for admin_id in ADMIN_IDS:
            try:
                await ctx.bot.send_message(
                    chat_id=admin_id,
                    text=f"🎉 <b>{order_id}</b> — yetkazildi ✅",
                    parse_mode="HTML"
                )
            except: pass

# ═══════════════════════════════════════════════
#   Admin/Kuryer panel
# ═══════════════════════════════════════════════
async def show_admin_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    total     = len(orders)
    pending   = sum(1 for o in orders.values() if o["status"] == Status.PENDING)
    confirmed = sum(1 for o in orders.values() if o["status"] == Status.CONFIRMED)
    revenue   = sum(o["total"] for o in orders.values() if o["status"] in [Status.CONFIRMED, Status.DELIVERED, Status.ON_THE_WAY])

    await update.message.reply_text(
        f"👨‍💼 <b>Admin Panel</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 Jami: <b>{total}</b> buyurtma\n"
        f"⏳ Kutilmoqda: <b>{pending}</b>\n"
        f"✅ Tasdiqlangan: <b>{confirmed}</b>\n"
        f"💰 Daromad: <b>{revenue:,} so'm</b>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([[
            InlineKeyboardButton("🛍 Mini App", web_app={"url": MINI_APP_URL})
        ]])
    )

async def show_courier_panel(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    active = [o for o in orders.values() if o["status"] in [Status.CONFIRMED, Status.ON_THE_WAY]]
    await update.message.reply_text(
        f"🚗 <b>Kuryer Panel</b>\n"
        f"━━━━━━━━━━━━━━━━━━\n"
        f"📦 Faol yetkazishlar: <b>{len(active)}</b>",
        parse_mode="HTML"
    )

# ═══════════════════════════════════════════════
#   /orders — admin buyurtmalar ro'yxati
# ═══════════════════════════════════════════════
async def cmd_orders(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    if not is_admin(uid):
        await update.message.reply_text("⛔ Ruxsat yo'q")
        return
    if not orders:
        await update.message.reply_text("📭 Hali buyurtma yo'q")
        return
    recent = list(orders.values())[-10:]
    text = "<b>Oxirgi buyurtmalar:</b>\n━━━━━━━━━━━━━━━━━━\n"
    status_emoji = {Status.PENDING:"⏳", Status.CONFIRMED:"✅", Status.ON_THE_WAY:"🚗", Status.DELIVERED:"🎉", Status.CANCELLED:"❌"}
    for o in reversed(recent):
        emoji = status_emoji.get(o["status"], "❓")
        text += f"{emoji} <b>{o['id']}</b> — {o['name']} — {o['total']:,} so'm\n"
    await update.message.reply_text(text, parse_mode="HTML")

# ═══════════════════════════════════════════════
#   MAIN
# ═══════════════════════════════════════════════
def main():
    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start",  cmd_start))
    app.add_handler(CommandHandler("orders", cmd_orders))
    app.add_handler(MessageHandler(filters.StatusUpdate.WEB_APP_DATA, web_app_data))
    app.add_handler(MessageHandler(filters.PHOTO, handle_photo))
    app.add_handler(MessageHandler(filters.LOCATION, handle_location))
    app.add_handler(CallbackQueryHandler(callback_handler))

    logger.info("🍰 Dilux Bakery Bot ishga tushdi!")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
