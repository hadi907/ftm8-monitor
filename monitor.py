import requests, smtplib, os, json
from email.mime.text import MIMEText
from datetime import datetime

API_URL    = "https://ftm8.com/api/orders?limit=20&sort=-createdAt&depth=1"
STATE_FILE = "last_order_id.txt"

GMAIL_USER   = os.environ["GMAIL_USER"]
GMAIL_PASS   = os.environ["GMAIL_PASS"]
NOTIFY_EMAIL = os.environ["NOTIFY_EMAIL"]
WA_PHONE     = os.environ["WA_PHONE"]
WA_APIKEY    = os.environ["WA_APIKEY"]


def load_last_id():
    if os.path.exists(STATE_FILE):
        return open(STATE_FILE).read().strip()
    return None


def save_last_id(order_id):
    with open(STATE_FILE, "w") as f:
        f.write(order_id)


def send_email(order):
    cust  = order.get("customerDetails", {})
    items = order.get("items", [])
    items_text = "\n".join(
        f"  - {i.get('product', {}).get('name', 'منتج')} × {i.get('quantity', 1)}  ({i.get('price', 0)} KWD)"
        for i in items
    )
    body = f"""
🛍️ طلب جديد من ftm8.com

👤 العميل : {cust.get('name', '—')}
📞 الهاتف : {cust.get('phone', '—')}
💰 الإجمالي: {order.get('total', 0):.3f} KWD
💳 الدفع  : {order.get('paymentMethod', '—')}
📦 الحالة : {order.get('status', '—')}

المنتجات:
{items_text}

🔗 https://ftm8.com/admin/collections/orders/{order.get('id','')}
    """.strip()

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = f"🛍️ طلب جديد — {cust.get('name','عميل')} — {order.get('total',0):.3f} KWD"
    msg["From"]    = GMAIL_USER
    msg["To"]      = NOTIFY_EMAIL

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_PASS)
        s.send_message(msg)
    print("✅ Email sent")


def send_whatsapp(order):
    cust  = order.get("customerDetails", {})
    items = order.get("items", [])
    items_text = " | ".join(
        f"{i.get('product',{}).get('name','منتج')} x{i.get('quantity',1)}"
        for i in items
    )
    text = (
        f"🛍️ طلب جديد ftm8\n"
        f"👤 {cust.get('name','—')}  📞 {cust.get('phone','—')}\n"
        f"💰 {order.get('total',0):.3f} KWD | {order.get('status','—')}\n"
        f"📦 {items_text}"
    )
    url = "https://api.callmebot.com/whatsapp.php"
    params = {"phone": WA_PHONE, "text": text, "apikey": WA_APIKEY}
    r = requests.get(url, params=params, timeout=15)
    print(f"✅ WhatsApp sent: {r.status_code}")


def main():
    print(f"[{datetime.utcnow().isoformat()}] Checking orders...")
    r = requests.get(API_URL, timeout=15)
    r.raise_for_status()
    docs = r.json().get("docs", [])

    if not docs:
        print("No orders found.")
        return

    last_id = load_last_id()
    newest  = docs[0]

    if newest["id"] == last_id:
        print("No new orders.")
        return

    # Find all orders newer than last known
    new_orders = []
    for order in docs:
        if order["id"] == last_id:
            break
        new_orders.append(order)

    print(f"🆕 {len(new_orders)} new order(s) found!")

    for order in reversed(new_orders):  # oldest first
        try:
            send_email(order)
        except Exception as e:
            print(f"❌ Email error: {e}")
        try:
            send_whatsapp(order)
        except Exception as e:
            print(f"❌ WhatsApp error: {e}")

    save_last_id(newest["id"])
    print("Done.")


if __name__ == "__main__":
    main()
