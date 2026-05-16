import os, json, requests
from datetime import datetime

FTM8_EMAIL = os.environ.get('FTM8_EMAIL', '')
FTM8_PASS = os.environ.get('FTM8_PASS', '')
FTM8_URL = 'https://ftm8.com'
SYNCED_FILE = 'ftm8_synced_sales.json'
DATA_FILE = 'farm_data.json'

def log(msg):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

def load_synced():
    if os.path.exists(SYNCED_FILE):
        with open(SYNCED_FILE) as f:
            return json.load(f)
    return {}

def save_synced(data):
    with open(SYNCED_FILE, 'w') as f:
        json.dump(data, f, indent=2)

def ftm8_login():
    try:
        r = requests.post(FTM8_URL + '/api/users/login',
            json={'email': FTM8_EMAIL, 'password': FTM8_PASS}, timeout=10)
        d = r.json()
        if 'token' in d:
            log("ftm8 login OK")
            return d['token']
        log("ftm8 login failed: " + str(d))
    except Exception as e:
        log("ftm8 login error: " + str(e))
    return None

def ftm8_headers(token):
    return {'Content-Type': 'application/json', 'Authorization': 'JWT ' + token}

def ftm8_find_product(sku, token):
    try:
        r = requests.get(FTM8_URL + '/api/products',
            params={'where[sku][equals]': sku, 'limit': 1},
            headers=ftm8_headers(token), timeout=10)
        d = r.json()
        if d.get('docs'):
            return d['docs'][0]['id']
    except Exception as e:
        log("find product error: " + str(e))
    return None

def ftm8_create_order(sale, inv_map, token):
    inv_item = inv_map.get(sale.get('invItemId', ''))
    sku = inv_item.get('sku') if inv_item else None
    ftm8_pid = ftm8_find_product(sku, token) if sku else None
    items = []
    if ftm8_pid:
        items = [{'product': ftm8_pid, 'quantity': sale.get('qty', 1), 'priceAtPurchase': sale.get('price', 0)}]
    payment = sale.get('payment', '')
    payload = {
        'status': 'قيد الانتظار',
        'paymentMethod': 'نقد' if payment in ['نقد', 'كاش'] else 'دفع إلكتروني',
        'total': sale.get('total', 0),
        'totalBeforeDiscount': sale.get('qty', 1) * sale.get('price', 0),
        'currency': 'KWD',
        'address': sale.get('location') or 'مزرعة هادي اسحاق',
        'items': items,
        'notes': 'مزامنة مزرعة - ' + str(sale.get('invNum', '')) + ' | ' + str(sale.get('client', ''))
    }
    try:
        r = requests.post(FTM8_URL + '/api/orders',
            json=payload, headers=ftm8_headers(token), timeout=10)
        d = r.json()
        oid = (d.get('doc') or {}).get('id') or d.get('id')
        if oid:
            log("Order created: " + str(oid))
            return oid
        log("Order not created: " + str(d)[:100])
    except Exception as e:
        log("create order error: " + str(e))
    return None

def ftm8_cancel_order(order_id, token):
    try:
        requests.patch(FTM8_URL + '/api/orders/' + order_id,
            json={'status': 'ملغي', 'notes': 'الغاء من تطبيق المزرعة'},
            headers=ftm8_headers(token), timeout=10)
        log("Order cancelled: " + str(order_id))
    except Exception as e:
        log("cancel error: " + str(e))

def load_farm_data():
    if os.path.exists(DATA_FILE):
        log("Reading from " + DATA_FILE)
        with open(DATA_FILE) as f:
            rec = json.load(f)
        sales = rec.get('SALES') or rec.get('ps3_sales') or []
        inv = rec.get('INV') or rec.get('ps3_inv') or []
        if isinstance(sales, str):
            try:
                sales = json.loads(sales)
            except Exception:
                sales = []
        if isinstance(inv, str):
            try:
                inv = json.loads(inv)
            except Exception:
                inv = []
        log(str(len(sales)) + " sales, " + str(len(inv)) + " inventory items")
        return sales, inv
    log(DATA_FILE + " not found")
    return [], []

def main():
    if not FTM8_EMAIL or not FTM8_PASS:
        log("Missing credentials")
        return
    sales, inv = load_farm_data()
    if not sales:
        log("No sales to sync")
        return
    inv_map = {item['id']: item for item in inv}
    synced = load_synced()
    token = ftm8_login()
    if not token:
        log("Cannot login to ftm8")
        return
    current_ids = {s['id'] for s in sales}
    for sid in list(synced.keys()):
        if sid not in current_ids:
            if synced[sid]:
                ftm8_cancel_order(synced[sid], token)
            del synced[sid]
    new_count = 0
    for sale in sales:
        sid = sale['id']
        if sid not in synced:
            oid = ftm8_create_order(sale, inv_map, token)
            synced[sid] = oid
            new_count += 1
    save_synced(synced)
    log("Done - " + str(new_count) + " new, " + str(len(synced)) + " total")

if __name__ == '__main__':
    main()
