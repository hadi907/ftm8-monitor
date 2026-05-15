import os, json, requests
from datetime import datetime

JSONBIN_URL = os.environ.get('JSONBIN_BIN_URL', '')
JSONBIN_KEY = os.environ.get('JSONBIN_API_KEY', '')
FTM8_EMAIL  = os.environ.get('FTM8_EMAIL', '')
FTM8_PASS   = os.environ.get('FTM8_PASS', '')
FTM8_URL    = 'https://ftm8.com'
SYNCED_FILE = 'ftm8_synced_sales.json'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

# ── Load synced IDs ──
def load_synced():
    if os.path.exists(SYNCED_FILE):
        with open(SYNCED_FILE) as f:
            return json.load(f)
    return {}  # {sale_id: ftm8_order_id}

def save_synced(data):
    with open(SYNCED_FILE, 'w') as f:
        json.dump(data, f, indent=2)

# ── ftm8 Login ──
def ftm8_login():
    try:
        r = requests.post(f'{FTM8_URL}/api/users/login',
            json={'email': FTM8_EMAIL, 'password': FTM8_PASS},
            timeout=10)
        d = r.json()
        if 'token' in d:
            log(f"✅ ftm8 login OK")
            return d['token']
        log(f"❌ ftm8 login failed: {d}")
    except Exception as e:
        log(f"❌ ftm8 login error: {e}")
    return None

def ftm8_headers(token):
    return {'Content-Type': 'application/json', 'Authorization': f'JWT {token}'}

# ── Find ftm8 product by SKU ──
def ftm8_find_product(sku, token):
    try:
        r = requests.get(f'{FTM8_URL}/api/products',
            params={'where[sku][equals]': sku, 'limit': 1},
            headers=ftm8_headers(token), timeout=10)
        d = r.json()
        if d.get('docs'):
            return d['docs'][0]['id']
    except Exception as e:
        log(f"⚠️ find product error: {e}")
    return None

# ── Create ftm8 order ──
def ftm8_create_order(sale, inv_map, token):
    inv_item = inv_map.get(sale.get('invItemId', ''))
    sku = inv_item.get('sku') if inv_item else None
    ftm8_product_id = ftm8_find_product(sku, token) if sku else None

    items = []
    if ftm8_product_id:
        items = [{'product': ftm8_product_id, 'quantity': sale.get('qty', 1), 'priceAtPurchase': sale.get('price', 0)}]

    payment = sale.get('payment', '')
    payload = {
        'status': 'قيد الانتظار',
        'paymentMethod': 'نقد' if payment in ['نقد', 'كاش'] else 'دفع إلكتروني',
        'total': sale.get('total', 0),
        'totalBeforeDiscount': sale.get('qty', 1) * sale.get('price', 0),
        'currency': 'KWD',
        'address': sale.get('location') or 'مزرعة هادي اسحاق',
        'items': items,
        'notes': f"مزامنة مزرعة — {sale.get('invNum','')} | {sale.get('client','')}"
    }
    try:
        r = requests.post(f'{FTM8_URL}/api/orders',
            json=payload, headers=ftm8_headers(token), timeout=10)
        d = r.json()
        oid = d.get('doc', {}).get('id') or d.get('id')
        if oid:
            log(f"✅ Order created: {oid} — {sale.get('product')} x{sale.get('qty')}")
            return oid
        log(f"⚠️ Order not created: {d}")
    except Exception as e:
        log(f"❌ create order error: {e}")
    return None

# ── Update ftm8 order ──
def ftm8_update_order(order_id, sale, token):
    payload = {
        'total': sale.get('total', 0),
        'notes': f"تعديل — {sale.get('invNum','')} | {sale.get('client','')}"
    }
    try:
        requests.patch(f'{FTM8_URL}/api/orders/{order_id}',
            json=payload, headers=ftm8_headers(token), timeout=10)
        log(f"🔄 Order updated: {order_id}")
    except Exception as e:
        log(f"❌ update order error: {e}")

# ── Cancel ftm8 order ──
def ftm8_cancel_order(order_id, token):
    try:
        requests.patch(f'{FTM8_URL}/api/orders/{order_id}',
            json={'status': 'ملغي', 'notes': 'تم الإلغاء من تطبيق المزرعة'},
            headers=ftm8_headers(token), timeout=10)
        log(f"🗑️ Order cancelled: {order_id}")
    except Exception as e:
        log(f"❌ cancel order error: {e}")

# ── Load farm data from JSONBin ──
def load_farm_data():
    try:
        headers = {}
        if JSONBIN_KEY:
            headers['X-Master-Key'] = JSONBIN_KEY
        r = requests.get(f'{JSONBIN_URL}/latest', headers=headers, timeout=15)
        d = r.json()
        rec = d.get('record', d)
        sales = rec.get('SALES', [])
        inv   = rec.get('INV', [])
        log(f"📦 Loaded {len(sales)} sales, {len(inv)} inventory items")
        return sales, inv
    except Exception as e:
        log(f"❌ JSONBin load error: {e}")
        return [], []

# ══ MAIN ══
def main():
    if not all([JSONBIN_URL, FTM8_EMAIL, FTM8_PASS]):
        log("❌ Missing environment variables"); return

    sales, inv = load_farm_data()
    if not sales:
        log("ℹ️ No sales found"); return

    inv_map = {item['id']: item for item in inv}
    synced  = load_synced()
    token   = ftm8_login()
    if not token:
        log("❌ Cannot proceed without ftm8 token"); return

    # Current sale IDs
    current_ids = {s['id'] for s in sales}

    # 1 — Cancel orders for deleted sales
    deleted = {sid: oid for sid, oid in synced.items() if sid not in current_ids}
    for sid, oid in deleted.items():
        if oid:
            ftm8_cancel_order(oid, token)
        del synced[sid]

    # 2 — Create or update orders
    for sale in sales:
        sid = sale['id']
        if sid not in synced:
            # New sale → create order
            oid = ftm8_create_order(sale, inv_map, token)
            synced[sid] = oid
        else:
            # Existing sale → check if total changed (edited)
            pass  # Could add hash check here for edits

    save_synced(synced)
    log(f"✅ Sync complete — {len(synced)} orders tracked")

if __name__ == '__main__':
    main()
