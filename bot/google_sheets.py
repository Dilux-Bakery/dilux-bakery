"""
Google Sheets integratsiyasi — yangi buyurtmalarni jadvalga yozadi.
Service Account orqali ishlaydi. Jadval foydalanuvchi tomonidan yaratilib,
SA email ga "Editor" qilib ulashilishi kerak (SA o'zi jadval yarata olmaydi).
"""
import logging

logger = logging.getLogger(__name__)

_ws = None
_enabled = False

HEADER = ["Vaqt", "ID", "Ism", "Telefon", "Mahsulotlar", "Yetkazish",
          "Manzil", "Yetkazish haqi", "Jami", "To'lov", "Holat"]

def init(sa_file: str, sheet_id: str):
    """Bot ishga tushganda chaqiriladi."""
    global _ws, _enabled
    if not sheet_id or not sa_file:
        logger.info("📊 Google Sheets sozlanmagan (SHEET_ID yo'q) — o'tkazib yuborildi")
        return
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(sa_file, scopes=scopes)
        gc = gspread.authorize(creds)
        _ws = gc.open_by_key(sheet_id).sheet1
        # Sarlavha bo'lmasa qo'shamiz
        try:
            if not _ws.row_values(1):
                _ws.append_row(HEADER, value_input_option="RAW")
        except Exception:
            pass
        _enabled = True
        logger.info("📊 Google Sheets ulandi")
    except Exception as e:
        logger.error(f"Sheets init xato: {e}")

def _pay(p):
    return {"card": "Karta", "click": "Click", "payme": "Payme"}.get(p, p or "—")

def _status(s):
    return {"pending": "Kutilmoqda", "confirmed": "Tasdiqlangan", "ready": "Tayyor",
            "on_the_way": "Yo'lda", "delivered": "Yetkazildi", "cancelled": "Bekor"}.get(s, s)

def append_order(o: dict):
    """Yangi buyurtmani jadvalga yozish (asosiy oqimni bloklamaydi)."""
    if not _enabled:
        return
    try:
        items = ", ".join(f"{i.get('emoji','')}{i.get('name','')}×{i.get('qty',0)}"
                          for i in o.get("items", []))
        dtype = "Yetkazib berish" if o.get("deliveryType") == "delivery" else "O'zi olib ketish"
        row = [
            o.get("time", ""), o.get("id", ""), o.get("name", ""),
            str(o.get("phone", "")), items, dtype, o.get("address", ""),
            int(o.get("deliveryFee", 0) or 0), int(o.get("total", 0) or 0),
            _pay(o.get("payment", "card")), _status(o.get("status", "pending")),
        ]
        _ws.append_row(row, value_input_option="RAW")
    except Exception as e:
        logger.error(f"Sheets append xato: {e}")

def update_status(order_id: str, status: str):
    """Buyurtma holatini jadvalda yangilash (ID ustuni bo'yicha topib)."""
    if not _enabled:
        return
    try:
        cell = _ws.find(str(order_id), in_column=2)  # B = ID
        if cell:
            _ws.update_cell(cell.row, 11, _status(status))  # K = Holat
    except Exception as e:
        logger.error(f"Sheets status xato: {e}")
