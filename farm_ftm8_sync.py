import os, json, requests
from datetime import datetime

FTM8_EMAIL  = os.environ.get('FTM8_EMAIL', '')
FTM8_PASS   = os.environ.get('FTM8_PASS', '')
FTM8_URL    = 'https://ftm8.com'
SYNCED_FILE = 'ftm8_synced_sales.json'
DATA_FILE   = 'farm_data.json'

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
        r = requests.post(f'{FTM8_URL}/api/users/login',
            json={'email': FTM8_EMAIL, 'password': FTM8_PASS}, timeout=10)
        d = r.json()
        if 'token' in d:
            log("✅ ftm8 login OK")
            return d['token']
        log(f"❌ ftm8 login failed: {d}")
    except Exception as e:
        log(f"❌ ftm8 login error: {e}")
    return None

def ftm8_headers(token):
    return {'Content-Type': 'application/json', 'Authorization': f'JWT {token}'}

def ftm8_find_product(sku, token):
    try:
        r = requests.get(f'{FTM8_URL}/api/products',
