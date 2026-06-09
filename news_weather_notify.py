import os
import requests
import urllib.parse
from datetime import datetime, timezone, timedelta

# ─── الإعدادات ────────────────────────────────────────────────
OWM_API_KEY      = os.environ.get("OWM_API_KEY", "").strip()
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

CITIES = [
    {"name": "الأحمدي", "q_owm": "Al Ahmadi,KW",  "q_wttr": "Al-Ahmadi"},
    {"name": "الوفرة",  "q_owm": "Al Wafra,KW",   "q_wttr": "Al-Wafra"},
]

NEWS_SOURCES = [
    {"name": "الجزيرة",   "url": "https://www.aljazeera.net/feed/mostviewed"},
    {"name": "BBC عربي",  "url": "https://feeds.bbci.co.uk/arabic/rss.xml"},
    {"name": "سكاي نيوز", "url": "https://www.skynewsarabia.com/rss.xml"},
    {"name": "KUNA",      "url": "https://www.kuna.net.kw/rss/rssfeeds.aspx?l=ar"},
]

# ─── تشخيص ───────────────────────────────────────────────────
print(f"DEBUG TOKEN length: {len(TELEGRAM_TOKEN)} | first5: {TELEGRAM_TOKEN[:5]}")
print(f"DEBUG CHAT_ID: '{TELEGRAM_CHAT_ID}'")

# ─── جلب الطقس ───────────────────────────────────────────────
def get_weather_owm(city):
    url = (f"https://api.openweathermap.org/data/2.5/weather"
           f"?q={urllib.parse.quote(city['q_owm'])}"
           f"&appid={OWM_API_KEY}&units=metric&lang=ar")
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    d = r.json()
    if d.get("cod") != 200:
        raise ValueError(d.get("message"))
    temp     = round(d["main"]["temp"])
    feels    = round(d["main"]["feels_like"])
    humidity = d["main"]["humidity"]
    wind     = round(d["wind"]["speed"] * 3.6)
    desc     = d["weather"][0]["description"]
    main_w   = d["weather"][0]["main"].lower()
    icon = ("☀️" if "clear" in main_w else "⛅" if "cloud" in main_w else
            "🌧️" if "rain" in main_w else "🌫️" if "haze" in main_w or "dust" in main_w else "🌡️")
    return (f"{icon} *{city['name']}:* {temp}°م (يبدو {feels}°م)\n"
            f"   💧 {humidity}%  💨 {wind} كم/س  | {desc}")

def get_weather_wttr(city):
    url = f"https://wttr.in/{city['q_wttr']}?format=j1"
    r = requests.get(url, timeout=10, headers={"User-Agent": "curl/7.0"})
    r.raise_for_status()
    d = r.json()
    cur      = d["current_condition"][0]
    temp     = cur["temp_C"]
    feels    = cur["FeelsLikeC"]
    humidity = cur["humidity"]
    wind     = cur["windspeedKmph"]
    desc     = cur["weatherDesc"][0]["value"]
    code     = int(cur["weatherCode"])
    icon = ("☀️" if code == 113 else "⛅" if code in [116,119,122] else
            "🌧️" if code >= 263 else "🌡️")
    return (f"{icon} *{city['name']}:* {temp}°م (يبدو {feels}°م)\n"
            f"   💧 {humidity}%  💨 {wind} كم/س  | {desc}")

def get_weather():
    lines = ["☁️ *الطقس الآن*"]
    for city in CITIES:
        try:
            if OWM_API_KEY:
                lines.append(get_weather_owm(city))
            else:
                raise ValueError("no key")
        except Exception:
            try:
                lines.append(get_weather_wttr(city))
            except Exception:
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

# ─── إرسال تيليغرام ──────────────────────────────────────────
def send_telegram(message: str):
    url  = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "Markdown"}
    r = requests.post(url, json=data, timeout=15)
    print(f"Telegram: {r.status_code} | {r.text[:200]}")
    return r.status_code == 200

# ─── التجميع والإرسال ────────────────────────────────────────
def main():
    kuwait_tz = timezone(timedelta(hours=3))
    now_kw    = datetime.now(kuwait_tz)
    now       = now_kw.strftime("%A، %d %B %Y — %I:%M %p")
    period    = "🌅 الصباحية" if now_kw.hour < 12 else "🌆 المسائية"

    header  = f"*📋 نشرة {period}*\n_{now}_\n"
    weather = get_weather()
    news    = get_news()

    full_message = f"{header}\n{weather}\n\n{news}"

    print("─── الرسالة ───────────────────────")
    print(full_message)
    print("───────────────────────────────────")

    ok = send_telegram(full_message)
    print("✅ أُرسلت بنجاح!" if ok else "❌ فشل الإرسال")

if __name__ == "__main__":
    main()
