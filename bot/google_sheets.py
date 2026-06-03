"""
Google Sheets integratsiyasi — yangi buyurtmalarni jadvalga yozadi.
Service Account orqali ishlaydi. Jadval foydalanuvchi tomonidan yaratilib,
SA email ga "Editor" qilib ulashilishi kerak (SA o'zi jadval yarata olmaydi).
"""
import logging

logger = logging.getLogger(__name__)

_ws = None
_sh = None
_enabled = False

HEADER = ["ID", "Sana", "Vaqt", "Mijoz", "Telefon", "Mahsulotlar",
          "Tur", "Manzil", "Yetkazish", "Jami (so'm)", "To'lov", "Holat"]

def init(sa_file: str, sheet_id: str):
    """Bot ishga tushganda chaqiriladi."""
    global _ws, _sh, _enabled
    if not sheet_id or not sa_file:
        logger.info("📊 Google Sheets sozlanmagan (SHEET_ID yo'q) — o'tkazib yuborildi")
        return
    try:
        import gspread
        from google.oauth2.service_account import Credentials
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(sa_file, scopes=scopes)
        gc = gspread.authorize(creds)
        _sh = gc.open_by_key(sheet_id)
        _ws = _sh.sheet1
        _enabled = True
        logger.info("📊 Google Sheets ulandi")
    except Exception as e:
        logger.error(f"Sheets init xato: {e}")

def _hex(h):
    h = h.lstrip("#")
    return {"red": int(h[0:2],16)/255, "green": int(h[2:4],16)/255, "blue": int(h[4:6],16)/255}

def _ensure_tahlil():
    """'Tahlil' varag'ini olib keladi; yo'q bo'lsa yaratib, sarlavhalarni qo'yadi."""
    try:
        ws = _sh.worksheet("Tahlil")
    except Exception:
        ws = _sh.add_worksheet(title="Tahlil", rows=60, cols=6)
        tid = ws.id
        ws.update(range_name="A1", values=[["MAHSULOTLAR TAHLILI"]])
        ws.update(range_name="A2", values=[["Mahsulot","Dona","Daromad (so'm)","Ulush %","Tahlil"]])
        reqs = [
          {"mergeCells":{"range":{"sheetId":tid,"startRowIndex":0,"endRowIndex":1,"startColumnIndex":0,"endColumnIndex":5},"mergeType":"MERGE_ALL"}},
          {"repeatCell":{"range":{"sheetId":tid,"startRowIndex":0,"endRowIndex":1,"startColumnIndex":0,"endColumnIndex":5},"cell":{"userEnteredFormat":{"backgroundColor":_hex("1a1208"),"horizontalAlignment":"CENTER","textFormat":{"foregroundColor":_hex("e8c97a"),"bold":True,"fontSize":14}}},"fields":"userEnteredFormat(backgroundColor,horizontalAlignment,textFormat)"}},
          {"repeatCell":{"range":{"sheetId":tid,"startRowIndex":1,"endRowIndex":2,"startColumnIndex":0,"endColumnIndex":5},"cell":{"userEnteredFormat":{"backgroundColor":_hex("3d2b1f"),"textFormat":{"foregroundColor":_hex("ffffff"),"bold":True}}},"fields":"userEnteredFormat(backgroundColor,textFormat)"}},
          {"updateSheetProperties":{"properties":{"sheetId":tid,"gridProperties":{"frozenRowCount":2}},"fields":"gridProperties.frozenRowCount"}},
          {"repeatCell":{"range":{"sheetId":tid,"startRowIndex":2,"startColumnIndex":2,"endColumnIndex":3},"cell":{"userEnteredFormat":{"numberFormat":{"type":"NUMBER","pattern":"#,##0"}}},"fields":"userEnteredFormat.numberFormat"}},
        ]
        for i,w in enumerate([180,90,130,80,260]):
            reqs.append({"updateDimensionProperties":{"range":{"sheetId":tid,"dimension":"COLUMNS","startIndex":i,"endIndex":i+1},"properties":{"pixelSize":w},"fields":"pixelSize"}})
        _sh.batch_update({"requests":reqs})
    return ws

def refresh_products(orders: dict):
    """Mahsulotlar tahlilini buyurtmalardan qayta hisoblab yozadi (avto-yangilanadi)."""
    if not _enabled:
        return
    try:
        ws = _ensure_tahlil()
        agg = {}
        for o in orders.values():
            if o.get("status") == "cancelled":
                continue
            for it in o.get("items", []):
                a = agg.setdefault(it.get("name",""), [0,0])
                a[0] += it.get("qty",0)
                a[1] += it.get("qty",0) * it.get("price",0)
        data = sorted([[n,v[0],v[1]] for n,v in agg.items()], key=lambda x:(-x[1],-x[2]))
        ws.batch_clear(["A3:E1000"])
        if data:
            totq = sum(d[1] for d in data) or 1
            totr = sum(d[2] for d in data)
            rows = []
            for i,(n,q,rev) in enumerate(data):
                tip = "🥇 Yetakchi" if i==0 else "🥈 2-o'rin" if i==1 else "🥉 3-o'rin" if i==2 else ("⚠️ Eng kam" if i==len(data)-1 else "✅ Barqaror")
                rows.append([n,q,rev,round(q*100/totq),tip])
            rows.append(["JAMI",totq,totr,100,""])
            ws.update(range_name="A3", values=rows, value_input_option="RAW")
    except Exception as e:
        logger.error(f"Tahlil refresh xato: {e}")

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
        ca = (o.get("created_at", "") or "")
        date = ca[:10]            # YYYY-MM-DD (bot vaqti — Toshkent)
        tm   = ca[11:16] or o.get("time", "")   # HH:MM
        row = [
            o.get("id", ""), date, tm, o.get("name", ""),
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
        cell = _ws.find(str(order_id), in_column=1)  # A = ID
        if cell:
            _ws.update_cell(cell.row, 12, _status(status))  # L = Holat
    except Exception as e:
        logger.error(f"Sheets status xato: {e}")
