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


def save_last_id(oid):
    open(STATE_FILE, "w").write(oid)


def send_email(order):
    cust = order.get("customerDetails", {})
    items = "\n".join(
        "  - " + i.get("product", {}).get("name", "item") +
        " x" + str(i.get("quantity", 1)) +
        " (" + str(i.get("price", 0)) + " KWD)"
        for i in order.get("items", [])
    )
    body = (
        "New Order - ftm8.com\n\n"
        "Customer: " + str(cust.get("name", "-")) + "\n"
        "Phone: " + str(cust.get("phone", "-")) + "\n"
        "Total: " + str(round(order.get("total", 0), 3)) + " KWD\n"
        "Payment: " + str(order.get("paymentMethod", "-")) + "\n"
        "Status: " + str(order.get("status", "-")) + "\n\n"
        "Items:\n" + items + "\n\n"
        "Link: " + BASE_URL + "/admin/collections/orders/" + order.get("id", "")
    )
    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = "New Order - " + str(cust.get("name", "")) + " - " + str(round(order.get("total", 0), 3)) + " KWD"
    msg["From"] = GMAIL_USER
    msg["To"] = NOTIFY_EMAIL
    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as s:
        s.login(GMAIL_USER, GMAIL_PASS)
        s.send_message(msg)
    print("Email sent")


def send_whatsapp(order):
    cust = order.get("customerDetails", {})
    items = " | ".join(
        i.get("product", {}).get("name", "item") + " x" + str(i.get("quantity", 1))
        for i in order.get("items", [])
    )
    text = ("New Order ftm8\n"
            "Name: " + str(cust.get("name", "-")) + " Tel: " + str(cust.get("phone", "-")) + "\n"
            "Total: " + str(round(order.get("total", 0), 3)) + " KWD | " + str(order.get("status", "-")) + "\n"
            "Items: " + items)
    requests.get("https://api.callmebot.com/whatsapp.php",
                 params={"phone": WA_PHONE, "text": text, "apikey": WA_APIKEY},
                 timeout=15)
    print("WA sent")


def main():
    print(datetime.utcnow().isoformat() + " Checking...")
    session = login()
    r = session.get(f"{BASE_URL}/api/orders?limit=20&sort=-createdAt&depth=1", timeout=15)
    r.raise_for_status()
    docs = r.json().get("docs", [])
    if not docs:
        print("No orders")
        return
    last_id = load_last_id()
    newest = docs[0]
    if newest["id"] == last_id:
        print("No new orders")
        return
    new_orders = []
    for o in docs:
        if o["id"] == last_id:
            break
        new_orders.append(o)
    print("New orders: " + str(len(new_orders)))
    for o in reversed(new_orders):
        try: send_email(o)
        except Exception as e: print("Email error: " + str(e))
        try: send_whatsapp(o)
        except Exception as e: print("WA error: " + str(e))
    save_last_id(newest["id"])
    print("Done")


if __name__ == "__main__":
    main()
