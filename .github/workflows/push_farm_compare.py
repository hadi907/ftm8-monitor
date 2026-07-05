import base64, requests, os

TOKEN = "ghp_3rl4QLYEdCb6JsWXVZ4P2QWdshG9Z0Nr7ty"
OWNER = "hadi907"
REPO  = "ftm8-monitor"
HDR   = {"Authorization": f"token {TOKEN}", "Accept": "application/vnd.github.v3+json"}

folder = os.path.dirname(os.path.abspath(__file__))
local_path  = os.path.join(folder, "farm_compare.py")
remote_path = "farm_compare.py"

def push_file(local_path, remote_path, label):
    api = f"https://api.github.com/repos/{OWNER}/{REPO}/contents/{remote_path}"
    with open(local_path, "rb") as f:
        content = base64.b64encode(f.read()).decode()
    sha = ""
    r = requests.get(api, headers=HDR, timeout=15)
    if r.status_code == 200:
        sha = r.json().get("sha", "")
    elif r.status_code != 404:
        print(f"⚠️ تحذير عند القراءة: {r.status_code} — {r.text[:200]}")
    body = {"message": f"إصلاح {remote_path} — تجاهل الفواتير القديمة خارج نطاق آخر 50 فاتورة (JSONBin)", "content": content}
    if sha:
        body["sha"] = sha
    r = requests.put(api, headers=HDR, json=body, timeout=60)
    if r.status_code in (200, 201):
        print(f"✅ {label} — تم الرفع بنجاح!")
    else:
        print(f"❌ {label} — فشل: {r.status_code} — {r.text[:300]}")

if not os.path.exists(local_path):
    print(f"❌ لم يُعثر على الملف: {local_path}")
else:
    print(f"📄 رفع: {remote_path}")
    push_file(local_path, remote_path, "farm_compare.py")
