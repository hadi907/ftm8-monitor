import requests, os, time
from datetime import datetime

BASE_URL    = "https://ftm8.com"
JSONBIN_URL = os.environ["JSONBIN_BIN_URL"]
JSONBIN_KEY = os.environ["JSONBIN_API_KEY"]
WA_PHONE    = os.environ["WA_PHONE"]
WA_APIKEY   = os.environ["WA_APIKEY"]
ADMIN_EMAIL = os.environ["ADMIN_EMAIL"]
ADMIN_PASS  = os.environ["ADMIN_PASS"]

STATE_KEY = "__last_sale_id__"

def get_data_from_jsonbin():
    r = requests.get(JSONBIN_URL,
                     headers={"X-Master-Key": JSONBIN_KEY},
                     timeout=15)
    r.raise_for_status()
    record = r.json().get("record", {})
    sales  = record.get("ps3_sales", [])
    return sales, record

def save_last_id_to_jsonbin(sid, current_record):
    try:
        current_record[STATE_KEY] = sid
        requests.put(JSONBIN_URL,
                     json=current_record,
                     headers={"X-Master-Key": JSONBIN_KEY,
                               "Content-Type": "application/json"},
                     timeout=15)
        print(f"State saved: {sid}")
    except Exception as e:
        print(f"Save state error: {e}")

def login():
    session = requests.Session()
    r = session.post(f"{BASE_URL}/api/users/login",
                     json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
                     timeout=15)
    r.raise_for_status()
    token = r.json().get("token")
    if token:
        session.headers.update({"Authorization": f"JWT {token}"})
        print("Login OK")
    return session

def create_ftm8_order(session, sale):
    client = sale.get("client", "نقدا") or "نقدا"
    payload = {
        "status": "pending",
        "paymentMethod": "cash_on_delivery",
        "total": sale.get("total", 0),
        "currency": "KWD",
        "address": sale.get("location", "مزرعة هادي اسحاق"),
        "notes": f"مزرعة — {sale.get('invNum', '')} | {client}",
        "customerDetails": {
            "name": client,
            "email": "farm@mazraa.kw",
            "phone": sale.get("phone", "00000000")
        }
    }
    r = session.post(f"{BASE_URL}/api/orders", json=payload, timeout=15)
    if r.status_code in [200, 201]:
        oid = (r.json().get("doc") or r.json()).get("id", "")
        print(f"ftm8 order created: {oid[:8] if oid else 'OK'}")
    else:
        print(f"ftm8 error: {r.status_code} — {r.text[:200]}")

def send_whatsapp_bulk(sales):
    """رسالة واحدة مجمّعة لكل البيعات الجديدة"""
    now   = datetime.utcnow().strftime("%Y-%m-%d %H:%M")
    total_kwd = round(sum(s.get("total", 0) for s in sales), 3)

    lines = [f"🌿 مزرعة هادي — {len(sales)} بيعة جديدة",
             f"🕐 {now} UTC",
             "─────────────────"]

    for sale in sales:
        product = sale.get("product", sale.get("invItemName", "—"))
        client  = sale.get("client", "نقدا") or "نقدا"
        qty     = sale.get("qty", 1)
        total   = round(sale.get("total", 0), 3)
        inv     = sale.get("invNum", "—")
        payment = sale.get("payment", "—")
        lines.append(f"📋 {inv}")
        lines.append(f"👤 {client} | 🪴 {product} x{qty}")
        lines.append(f"💰 {total} KWD | {payment}")
        lines.append("─────────────────")

    lines.append(f"📊 الإجمالي: {total_kwd} KWD")

    text = "\n".join(lines)
    r = requests.get("https://api.callmebot.com/whatsapp.php",
                     params={"phone": WA_PHONE, "text": text, "apikey": WA_APIKEY},
                     timeout=15)
    print(f"WA bulk sent: {r.status_code}")
    if r.status_code != 200:
        print(f"WA response: {r.text[:200]}")

def main():
    print(datetime.utcnow().isoformat() + " Checking...")

    try:
        sales, full_record = get_data_from_jsonbin()
    except Exception as e:
        print(f"JSONBin error: {e}"); return

    if not sales:
        print("No sales in JSONBin"); return

    # إزالة المكررات
    seen_ids = set()
    unique_sales = []
    for s in sales:
        sid = s.get("id")
        if sid and sid not in seen_ids:
            seen_ids.add(sid)
            unique_sales.append(s)

    sales_sorted = sorted(unique_sales,
                          key=lambda x: x.get("date", ""),
                          reverse=True)

    last_id = full_record.get(STATE_KEY, None)
    newest  = sales_sorted[0]

    if newest.get("id") == last_id:
        print("No new orders"); return

    new_sales = []
    for s in sales_sorted:
        if s.get("id") == last_id:
            break
        new_sales.append(s)

    # حد أقصى 10 بيعات للمعالجة
    if len(new_sales) > 10:
        print(f"Capped at 10 (found {len(new_sales)})")
        new_sales = new_sales[:10]

    print(f"New sales to process: {len(new_sales)}")

    # ftm8 — طلب لكل بيعة
    try:
        session = login()
    except Exception as e:
        print(f"Login error: {e}"); session = None

    for sale in reversed(new_sales):
        if session:
            try: create_ftm8_order(session, sale)
            except Exception as e: print(f"ftm8 error: {e}")

    # واتساب — رسالة واحدة مجمّعة ✅
    try:
        send_whatsapp_bulk(list(reversed(new_sales)))
    except Exception as e:
        print(f"WA error: {e}")

    save_last_id_to_jsonbin(newest["id"], full_record)
    print("Done")

if __name__ == "__main__":
    main()
