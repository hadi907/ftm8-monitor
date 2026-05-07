import requests, smtplib, os
from email.mime.text import MIMEText
from datetime import datetime

BASE_URL   = "https://ftm8.com"
STATE_FILE = "last_order_id.txt"

GMAIL_USER   = os.environ["GMAIL_USER"]
GMAIL_PASS   = os.environ["GMAIL_PASS"]
NOTIFY_EMAIL = os.environ["NOTIFY_EMAIL"]
WA_PHONE     = os.environ["WA_PHONE"]
WA_APIKEY    = os.environ["WA_APIKEY"]
ADMIN_EMAIL  = os.environ["ADMIN_EMAIL"]
ADMIN_PASS   = os.environ["ADMIN_PASS"]


def login():
    session = requests.Session()
    r = session.post(
        f"{BASE_URL}/api/users/login",
        json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
        timeout=15
    )
    r.raise_for_status()
    token = r.json().get("token")
    if token:
        session.headers.update({"Authorization": f"JWT {token}"})
        print("Logged in OK")
    return session


def load_last_id():
    if os.path.exists(STATE_FILE):
        return open(STATE_FILE).read().strip()
    return None


def save_last_id(order_id):
    with open(STATE_FILE, "w") as f:
        f.write(order_id)


def send_email(order):
    cust = order.get("customerDetails", {})
    items = order.get("items", [])
    items_text = "\n".join(
        f"  - {i.get('product', {}).get('name', 'منتج')} x{i.get('quantity', 1)} ({i.get('price', 0)} KWD)"
        for i in items
    )
    body = f"""طلب جديد من ftm8.com

العميل : {cust.get('name', '—')}
الهاتف : {cust.get('phone', '—')}
الاجمالي: {order.get('total', 0):.3f} KWD
الدفع  : {order.get('paymen
