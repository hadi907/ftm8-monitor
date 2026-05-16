import os, json, requests
from datetime import datetime

FTM8_EMAIL  = os.environ.get('FTM8_EMAIL', '')
FTM8_PASS   = os.environ.get('FTM8_PASS', '')
FTM8_URL    = 'https://ftm8.com'
SYNCED_FILE = 'ftm8_synced_sales.json'
DATA_FILE   = 'farm_data.json'

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
            log("ftm8 login OK")
            return d['token']
        log("ftm8 login failed: " + str(d))
    except
