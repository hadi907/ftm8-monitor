import requests, os, json
from datetime import datetime

# ── إعدادات ──────────────────────────────────────────────
JSONBIN_BIN_URL = os.environ["JSONBIN_BIN_URL"]   # مثال: https://api.jsonbin.io/v3/b/XXXX
JSONBIN_API_KEY = os.environ.get("JSONBIN_API_KEY", "")

WA_PHONE  = os.environ["WA_PHONE"]    # 96599014431
WA_APIKEY = os.environ["WA_APIKEY"]   # 1808268
# ─────────────────────────────────────────────────────────


def fetch_inventory():
    """جلب بيانات المخزون من JSONBin"""
    headers = {"X-Bin-Meta": "false"}
    if JSONBIN_API_KEY:
        headers["X-Master-Key"] = JSONBIN_API_KEY

    url = JSONBIN_BIN_URL + "/latest" if not JSONBIN_BIN_URL.endswith("/latest") else JSONBIN_BIN_URL
    r = requests.get(url, headers=headers, timeout=15)
    r.raise_for_status()
    data = r.json()

    # JSONBin يرجع البيانات مباشرة أو داخل record
    if "record" in data:
        data = data["record"]

    return data.get("INV", [])


def check_stock(inv):
    """تصنيف المخزون: نافد / منخفض / تحذير"""
    critical = [p for p in inv if (p.get("remaining") or 0) <= 0]
    low      = [p for p in inv if (p.get("remaining") or 0) > 0
                               and (p.get("remaining") or 0) <= (p.get("minStock") or 5)]
    warning  = [p for p in inv if (p.get("remaining") or 0) > (p.get("minStock") or 5)
                               and (p.get("remaining") or 0) <= (p.get("minStock") or 5) * 2]
    return critical, low, warning


def build_message(critical, low, warning):
    """بناء رسالة الواتس اب"""
    today = datetime.now().strftime("%Y-%m-%d  %H:%M")

    lines = [
        "🌿 *مزرعة هادي اسحاق — تنبيه مخزون*",
        f"📅 {today}",
        "━━━━━━━━━━━━━━━━━━━━━━",
    ]

    if critical:
        lines.append(f"🔴 *نفد المخزون ({len(critical)} صنف):*")
        for p in critical:
            lines.append(f"  • {p.get('name','—')} ❌ الكمية: صفر")
        lines.append("")

    if low:
        lines.append(f"🟠 *مخزون منخفض ({len(low)} صنف):*")
        for p in low:
            rem = p.get("remaining", 0)
            mn  = p.get("minStock") or 5
            lines.append(f"  • {p.get('name','—')} — المتبقي: *{rem}* (الحد: {mn})")
        lines.append("")

    if warning:
        lines.append(f"🟡 *يقترب النفاد ({len(warning)} صنف):*")
        for p in warning:
            lines.append(f"  • {p.get('name','—')} — المتبقي: {p.get('remaining',0)}")
        lines.append("")

    lines += [
        "━━━━━━━━━━━━━━━━━━━━━━",
        "📲 _تنبيه تلقائي — GitHub Actions_",
    ]
    return "\n".join(lines)


def send_whatsapp(text):
    """إرسال رسالة واتس اب عبر CallMeBot"""
    url = "https://api.callmebot.com/whatsapp.php"
    params = {
        "phone":  WA_PHONE,
        "text":   text,
        "apikey": WA_APIKEY,
    }
    r = requests.get(url, params=params, timeout=15)
    print(f"✅ WhatsApp sent — status: {r.status_code}")
    if r.status_code != 200:
        print(f"   Response: {r.text[:200]}")


def main():
    print(f"[{datetime.utcnow().isoformat()}] 🌿 فحص مخزون مزرعة هادي اسحاق...")

    inv = fetch_inventory()
    if not inv:
        print("⚠️  المخزون فارغ أو JSONBin غير مضبوط.")
        return

    print(f"📦 عدد الأصناف: {len(inv)}")

    critical, low, warning = check_stock(inv)
    print(f"🔴 نافد: {len(critical)} | 🟠 منخفض: {len(low)} | 🟡 تحذير: {len(warning)}")

    if not critical and not low:
        print("✅ المخزون بخير — لا يوجد تنبيه.")
        return

    msg = build_message(critical, low, warning)
    print("\n📨 الرسالة:\n" + msg + "\n")

    send_whatsapp(msg)
    print("✅ Done.")


if __name__ == "__main__":
    main()
