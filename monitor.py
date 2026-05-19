import requests, os
from datetime import datetime

BASE_URL       = "https://ftm8.com"
JSONBIN_URL    = os.environ["JSONBIN_BIN_URL"]
JSONBIN_KEY    = os.environ["JSONBIN_API_KEY"]
WA_PHONE       = os.environ["WA_PHONE"]
WA_APIKEY      = os.environ["WA_APIKEY"]
ADMIN_EMAIL    = os.environ["ADMIN_EMAIL"]
ADMIN_PASS     = os.environ["ADMIN_PASS"]
STATE_FILE     = "last_sale_id.txt"

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

def load_last_id():
    if os.path.exists(STATE_FILE):
        return open(STATE_FILE).read().strip()
    return None

def save_last_id(sid):
    open(STATE_FILE, "w").write(sid)

def get_sales_from_jsonbin():
    r = requests.get(JSONBIN_URL,
                     headers={"X-Master-Key": JSONBIN_KEY},
                     timeout=15)
    r.raise_for_status()
    data = r.json().get("record", {})
    return data.get("ps3_sales", [])

def create_ftm8_order(session, sale):
    client = sale.get("client", "نقدا") or "نقدا"
    payload = {
        "status": "pending",
        "paymentMethod": "cashOnDelivery",
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
    r = session.post(f"{BASE_URL}/api/orders",
                     json=payload, timeout=15)
    if r.status_code in [200, 201]:
        oid = (r.json().get("doc") or r.json()).get("id", "")
        print(f"ftm8 order created: {oid[:8] if oid else 'OK'}")
        return oid
    else:
        print(f"ftm8 error: {r.status_code} — {r.text[:200]}")
        return None

def send_whatsapp(sale):
    product = sale.get("product", sale.get("invItemName", "—"))
    client  = sale.get("client", "نقدا")
    qty     = sale.get("qty", 1)
    total   = round(sale.get("total", 0), 3)
    inv     = sale.get("invNum", "—")
    payment = sale.get("payment", "—")
    date    = sale.get("date", "")[:10]
    text = (f"🌿 بيعة جديدة — مزرعة هادي\n"
            f"📋 {inv} | {date}\n"
            f"👤 {client}\n"
            f"🪴 {product} x{qty}\n"
            f"💰 {total} KWD | {payment}")
    r = requests.get("https://api.callmebot.com/whatsapp.php",
                     params={"phone": WA_PHONE, "text": text, "apikey": WA_APIKEY},
                     timeout=15)
    print(f"WA sent: {r.status_code}")

def main():
    print(datetime.utcnow().isoformat() + " Checking...")
    try:
        sales = get_sales_from_jsonbin()
    except Exception as e:
        print(f"JSONBin error: {e}"); return

    if not sales:
        print("No sales in JSONBin"); return

    sales_sorted = sorted(sales, key=lambda x: x.get("date", ""), reverse=True)
    last_id = load_last_id()
    newest  = sales_sorted[0]

    if newest.get("id") == last_id:
        print("No new orders"); return

    new_sales = []
    for s in sales_sorted:
        if s.get("id") == last_id: break
        new_sales.append(s)

    print(f"New sales: {len(new_sales)}")

    try:
        session = login()
    except Exception as e:
        print(f"Login error: {e}"); session = None

    for sale in reversed(new_sales):
        if session:
            try: create_ftm8_order(session, sale)
            except Exception as e: print(f"ftm8 error: {e}")
        try: send_whatsapp(sale)
        except Exception as e: print(f"WA error: {e}")

    save_last_id(newest["id"])
    print("Done")

if __name__ == "__main__":
    main()
