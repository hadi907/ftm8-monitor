import os
import requests
import urllib.parse
from datetime import datetime

# ─── الإعدادات (تُقرأ من GitHub Secrets) ────────────────────
OWM_API_KEY     = os.environ.get("OWM_API_KEY",     "5e8b3da7a6b1559d239ccd37d4699a33")
CALLMEBOT_PHONE = os.environ.get("CALLMEBOT_PHONE", "+96599014431")
CALLMEBOT_KEY   = os.environ.get("CALLMEBOT_KEY",   "1808268")

CITIES = [
    {"name": "الأحمدي",  "id": "99798"},   # Al-Ahmadi, KW
    {"name": "الوفرة",   "id": "99777"},   # Al-Wafra, KW
]

NEWS_SOURCES = [
    {"name": "الجزيرة",      "url": "https://www.aljazeera.net/feed/mostviewed"},
    {"name": "BBC عربي",     "url": "https://feeds.bbci.co.uk/arabic/rss.xml"},
    {"name": "سكاي نيوز",    "url": "https://www.skynewsarabia.com/rss.xml"},
    {"name": "KUNA",         "url": "https://www.kuna.net.kw/rss/rssfeeds.aspx?l=ar"},
]

# ─── جلب الطقس ───────────────────────────────────────────────
def get_weather():
    lines = ["☁️ *الطقس الآن*"]
    for city in CITIES:
        try:
            url = (
                f"https://api.openweathermap.org/data/2.5/weather"
                f"?id={city['id']}&appid={OWM_API_KEY}&units=metric&lang=ar"
            )
            r = requests.get(url, timeout=10)
            d = r.json()
            temp     = round(d["main"]["temp"])
            feels    = round(d["main"]["feels_like"])
            humidity = d["main"]["humidity"]
            desc     = d["weather"][0]["description"]
            icon = "☀️" if "clear" in d["weather"][0]["main"].lower() else \
                   "⛅" if "cloud" in d["weather"][0]["main"].lower() else \
                   "🌧️" if "rain"  in d["weather"][0]["main"].lower() else "🌡️"
            lines.append(
                f"{icon} *{city['name']}:* {temp}°م | يبدو {feels}°م\n"
                f"   💧 رطوبة: {humidity}% | {desc}"
            )
        except Exception as e:
            lines.append(f"⚠️ {city['name']}: تعذّر جلب الطقس")
    return "\n".join(lines)

# ─── جلب الأخبار ─────────────────────────────────────────────
def get_news():
    import xml.etree.ElementTree as ET
    lines = ["📰 *أبرز الأخبار*"]
    for src in NEWS_SOURCES:
        try:
            r = requests.get(src["url"], timeout=10, headers={"User-Agent": "Mozilla/5.0"})
            root = ET.fromstring(r.content)
            items = root.findall(".//item")[:2]
            if not items:
                continue
            lines.append(f"\n🔹 *{src['name']}*")
            for item in items:
                title = item.findtext("title", "").strip()
                if title:
                    lines.append(f"  • {title}")
        except Exception:
            pass
    return "\n".join(lines)

# ─── إرسال واتساب ────────────────────────────────────────────
def send_whatsapp(message: str):
    encoded = urllib.parse.quote(message)
    url = (
        f"https://api.callmebot.com/whatsapp.php"
        f"?phone={CALLMEBOT_PHONE}&text={encoded}&apikey={CALLMEBOT_KEY}"
    )
    r = requests.get(url, timeout=15)
    return r.status_code == 200

# ─── التجميع والإرسال ────────────────────────────────────────
def main():
    now = datetime.now().strftime("%A، %d %B %Y — %I:%M %p")
    period = "🌅 الصباحية" if datetime.now().hour < 12 else "🌆 المسائية"

    header  = f"*📋 نشرة {period}*\n_{now}_\n"
    weather = get_weather()
    news    = get_news()

    full_message = f"{header}\n{weather}\n\n{news}"

    print("─── الرسالة ───────────────────────")
    print(full_message)
    print("───────────────────────────────────")

    ok = send_whatsapp(full_message)
    print("✅ أُرسلت بنجاح!" if ok else "❌ فشل الإرسال")

if __name__ == "__main__":
    main()
