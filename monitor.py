import os, sys, requests, json
from datetime import datetime

# ── Config from GitHub Secrets ──
WA_PHONE   = os.environ.get('WA_PHONE',  '')
WA_APIKEY  = os.environ.get('WA_APIKEY', '')
ADMIN_EMAIL = os.environ.get('ADMIN_EMAIL', '')
ADMIN_PASS  = os.environ.get('ADMIN_PASS',  '')

JSONBIN_URL = os.environ.get(
    'JSONBIN_BIN_URL',
    'https://api.jsonbin.io/v3/b/6a0c5f4b6877513b27993aed'
)
JSONBIN_KEY = os.environ.get(
    'JSONBIN_API_KEY',
    '$2a$10$hymkvXJ9AvDFIag8.j4sf.Qw..HkaR0Qd3KUFYkjkTMOqO6MM68DC'
)
FTM8_URL = 'https://ftm8.com'

JSONBIN_HEADERS = {
    'X-Master-Key': JSONBIN_KEY,
    'Content-Type': 'application/json'
}

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ── JSONBin: Read ──
def read_jsonbin():
    try:
        r = requests.get(JSONBIN_URL, headers=JSONBIN_HEADERS, timeout=15)
        if r.status_code == 200:
            return r.json().get('record', {})
    except Exception as e:
        log(f"JSONBin read error: {e}")
    return {}

# ── JSONBin: Write ──
def write_jsonbin(data):
    try:
        r = requests.put(JSONBIN_URL, headers=JSONBIN_HEADERS,
                         json=data, timeout=15)
        return r.status_code == 200
    except Exception as e:
        log(f"JSONBin write error: {e}")
    return False

# ── WhatsApp via CallMeBot ──
def send_whatsapp(msg):
    if not WA_PHONE or not WA_APIKEY:
        log("WhatsApp: no credentials, skipping")
        return
    try:
        url = (f"https://api.callmebot.com/whatsapp.php"
               f"?phone={requests.utils.quote(WA_PHONE)}"
               f"&text={requests.utils.quote(msg)}"
               f"&apikey={WA_APIKEY}")
        r = requests.get(url, timeout=20)
        log(f"WhatsApp sent: HTTP {r.status_code}")
    except Exception as e:
        log(f"WhatsApp error (non-fatal): {e}")

# ── ftm8: Login ──
def ftm8_login():
    if not ADMIN_EMAIL or not ADMIN_PASS:
        log("ftm8: no credentials")
        return None
    try:
        r = requests.post(
            f"{FTM8_URL}/api/users/login",
            json={"email": ADMIN_EMAIL, "password": ADMIN_PASS},
            timeout=15
        )
        d = r.json()
        if d.get('token'):
            log("ftm8: login OK")
            return d['token']
        log(f"ftm8: login failed — {d.get('message','unknown')}")
    except Exception as e:
        log(f"ftm8: login error (non-fatal): {e}")
    return None

# ── ftm8: Get pending orders ──
def ftm8_get_pending(token):
    try:
        headers = {'Authorization': f'JWT {token}'}
        r = requests.get(
            f"{FTM8_URL}/api/orders"
            f"?where[status][equals]=pending"
            f"&where[paymentMethod][equals]=cash_on_delivery"
            f"&limit=20&sort=-createdAt",
            headers=headers, timeout=15
        )
        if r.status_code == 200:
            return r.json().get('docs', [])
    except Exception as e:
        log(f"ftm8 orders error (non-fatal): {e}")
    return []

# ── ftm8: Create order ──
def ftm8_create_order(token, sale):
    try:
        payload = {
            "status": "pending",
            "paymentMethod": "cash_on_delivery",
            "total": sale.get('total', 0),
            "currency": "KWD",
            "customerDetails": {
                "name":  sale.get('client', 'عميل المزرعة'),
                "email": "farm@hadi.com",
                "phone": sale.get('phone', '00000000')
            },
            "notes": f"مزامنة مزرعة — {sale.get('invNum','')} {sale.get('client','')}"
        }
        r = requests.post(
            f"{FTM8_URL}/api/orders",
            headers={'Authorization': f'JWT {token}',
                     'Content-Type': 'application/json'},
            json=payload, timeout=15
        )
        d = r.json()
        oid = (d.get('doc') or {}).get('id') or d.get('id')
        if oid:
            log(f"ftm8: order created #{oid[-6:]}")
            return oid
        log(f"ftm8: create failed — {d}")
    except Exception as e:
        log(f"ftm8: create error (non-fatal): {e}")
    return None

# ══════════════════════════════════
#           MAIN LOGIC
# ══════════════════════════════════
def main():
    log("=== ftm8 Monitor Start ===")

    # 1. Read data from JSONBin
    data = read_jsonbin()
    if not data:
        log("JSONBin: empty or unreachable — exit OK")
        return

    sales = data.get('ps3_sales', [])
    last_id = data.get('__last_sale_id__', '')

    log(f"Total sales in JSONBin: {len(sales)}")
    log(f"Last processed ID: {last_id or 'none'}")

    if not sales:
        log("No sales data — exit OK")
        return

    # 2. Find new sales after last_id
    new_sales = []
    if not last_id:
        # First run: mark latest as seen, don't notify old data
        latest = sales[-1]
        new_last_id = latest.get('id', '')
        log(f"First run — marking latest as seen: {new_last_id}")
        data['__last_sale_id__'] = new_last_id
        write_jsonbin(data)
        log("No notification on first run — exit OK")
        return
    else:
        # Find index of last_id
        ids = [s.get('id','') for s in sales]
        if last_id in ids:
            idx = ids.index(last_id)
            new_sales = sales[idx+1:]
        else:
            # last_id not found — take last 5 max (safety)
            new_sales = sales[-5:]

    # Remove duplicates by ID
    seen = set()
    unique_new = []
    for s in new_sales:
        sid = s.get('id','')
        if sid and sid not in seen:
            seen.add(sid)
            unique_new.append(s)

    log(f"New sales found: {len(unique_new)}")

    if not unique_new:
        log("No new sales — exit OK (no notification)")
        return

    # 3. Login to ftm8
    token = ftm8_login()

    # 4. Process new sales
    lines = ['🌿 مبيعات جديدة — مزرعة هادي']
    for s in unique_new[:10]:  # max 10 per run
        name   = s.get('itemName', s.get('name', 'صنف'))
        qty    = s.get('qty', 0)
        total  = s.get('total', 0)
        client = s.get('client', '')
        invnum = s.get('invNum', '')
        line = f"• {name} × {qty} = {total} د.ك"
        if client: line += f" | {client}"
        if invnum: line += f" | {invnum}"
        lines.append(line)

        # Create order in ftm8
        if token:
            ftm8_create_order(token, s)

    # 5. Send WhatsApp (one message)
    msg = '\n'.join(lines)
    log(f"Sending WhatsApp:\n{msg}")
    send_whatsapp(msg)

    # 6. Update last_id in JSONBin
    new_last = unique_new[-1].get('id', last_id)
    data['__last_sale_id__'] = new_last
    if write_jsonbin(data):
        log(f"JSONBin updated — new last_id: {new_last}")
    else:
        log("JSONBin update failed (non-fatal)")

    log("=== Done ===")

# ── Entry Point ──
if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        # NEVER exit with error code — prevents failure emails
        log(f"Unexpected error (caught): {e}")
        import traceback
        traceback.print_exc()

    sys.exit(0)  # Always exit 0
