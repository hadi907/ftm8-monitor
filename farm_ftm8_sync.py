import os, json, requests
from datetime import datetime

FTM8_EMAIL = os.environ.get('FTM8_EMAIL', '')
FTM8_PASS = os.environ.get('FTM8_PASS', '')
FTM8_URL = 'https://ftm8.com'
SYNCED_FILE = 'ftm8_synced_sales.json'
DATA_FILE = 'farm_data.json'

def log(msg):
    print("[" + datetime.now().strftime('%H:%M:%S') + "] " + str(msg))

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
            log("login OK")
            return d['token']
        log("login failed: " + str(d))
    except Exception as e:
        log("login error: " + str(e))
    return None

def headers(token):
    return {'Content-Type': 'application/json', 'Authorization': 'JWT ' + token}

def find_product(sku, token):
    try:
        r = requests.get(FTM8_URL + '/api/products',
            params={'where[sku][equals]': sku, 'limit': 1},
            headers=headers(token), timeout=10)
        docs = r.json().get('docs', [])
        if docs:
            return docs[0]['id']
    except Exception as e:
        log("find_product error: " + str(e))
    return None

def create_order(sale, inv_map, token):
    item = inv_map.get(sale.get('invItemId', ''))
    sku = item.get('sku') if item else None
    pid = find_product(sku, token) if sku else None
    items = []
    if pid:
        items = [{'product': pid, 'quantity': sale.get('qty', 1), 'priceAtPurchase': sale.get('price', 0)}]
    pay = sale.get('payment', '')
    body = {
        'status': 'pending',
        'paymentMethod': 'cash' if pay in ['نقد', 'كاش'] else 'card',
        'total': sale.get('total', 0),
        'totalBeforeDiscount': sale.get('qty', 1) * sale.get('price', 0),
        'currency': 'KWD',
        'address': sale.get('location') or 'مزرعة هادي اسحاق',
        'items': items,
        'notes': 'مزامنة - ' + str(sale.get('invNum', '')) + ' | ' + str(sale.get('client', ''))
    }
    try:
        r = requests.post(FTM8_URL + '/api/orders', json=body, headers=headers(token), timeout=10)
        d = r.json()
        oid = (d.get('doc') or {}).get('id') or d.get('id')
        if oid:
            log("created: " + str(oid))
            return oid
        log("not created: " + str(d)[:300])
    except Exception as e:
        log("create error: " + str(e))
    return None

def cancel_order(oid, token):
    try:
        requests.patch(FTM8_URL + '/api/orders/' + oid,
            json={'status': 'cancelled'}, headers=headers(token), timeout=10)
        log("cancelled: " + str(oid))
    except Exception as e:
        log("cancel error: " + str(e))

def load_data():
    if not os.path.exists(DATA_FILE):
        log(DATA_FILE + " not found")
        return [], []
    with open(DATA_FILE) as f:
        rec = json.load(f)
    log("Keys: " + str(list(rec.keys())))
    sales = rec.get('SALES') or rec.get('ps3_sales') or []
    inv = rec.get('INV') or rec.get('ps3_inv') or []
    if isinstance(sales, str):
        try: sales = json.loads(sales)
        except: sales = []
    if isinstance(inv, str):
        try: inv = json.loads(inv)
        except: inv = []
    log(str(len(sales)) + " sales, " + str(len(inv)) + " items")
    return sales, inv

def main():
    if not FTM8_EMAIL or not FTM8_PASS:
        log("Missing credentials")
        return
    sales, inv = load_data()
    if not sales:
        log("No sales")
        return
    inv_map = {x['id']: x for x in inv}
    synced = load_synced()
    token = ftm8_login()
    if not token:
        log("Login failed")
        return
    current = {s['id'] for s in sales}
    for sid in list(synced.keys()):
        if sid not in current:
            if synced[sid]:
                cancel_order(synced[sid], token)
            del synced[sid]
    new = 0
    for sale in sales:
        sid = sale['id']
        if sid not in synced:
            oid = create_order(sale, inv_map, token)
            synced[sid] = oid
            new += 1
    save_synced(synced)
    log("Done - " + str(new) + " new, " + str(len(synced)) + " total")

if __name__ == '__main__':
    main()
