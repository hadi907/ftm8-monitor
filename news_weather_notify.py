import os
import requests
import urllib.parse
from datetime import datetime

# ─── الإعدادات ────────────────────────────────────────────────
CALLMEBOT_PHONE = os.environ.get("CALLMEBOT_PHONE", "+96599014431").strip()
CALLMEBOT_KEY   = os.environ.get("CALLMEBOT_KEY",   "1808268").strip()
OWM_API_KEY     = os.environ.get("OWM_API_KEY",     "").strip()

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

# ─── جلب الطقس (OWM أولاً، wttr.in كبديل) ───────────────────
def get_weather_owm(city):
    url = (
        f"https://api.openweathermap.org/data/2.5/weather"
        f"?q={urllib.parse.quote(city['q_owm'])}"
        f"&appid={OWM_API_KEY}&units=metric&lang=ar"
    )
    r = requests.get(url, timeout=10)
    r.raise_for_status()
    d = r.json()
    if d.get("cod") != 200:
        raise ValueError(d.get("message", "خطأ"))
    temp     = round(d["main"]["temp"])
    feels    = round(d["main"]["feels_like"])
    humidity = d["main"]["humidity"]
    wind     = round(d["wind"]["speed"] * 3.6)
    desc     = d["weather"][0]["description"]
    main_w   = d["weather"][0]["main"].lower()
    icon = ("☀️" if "clear" in main_w else
            "⛅" if "cloud" in main_w else
            "🌧️" if "rain"  in main_w else
            "🌫️" if "haze"  in main_w or "dust" in main_w else "🌡️")
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
    icon = "☀️" if int(cur["weatherCode"]) in [113] else \
           "⛅" if int(cur["weatherCode"]) in [116,119,122] else \
           "🌧️" if int(cur["weatherCode"]) >= 263 else "🌡️"
    return (f"{icon} *{city['name']}:* {temp}°م (يبدو {feels}°م)\n"
            f"   💧 {humidity}%  💨 {wind} كم/س  | {desc}")

def get_weather():
    lines = ["☁️ *الطقس الآن*"]
    for city in CITIES:
        try:
            if OWM_API_KEY:
                lines.append(get_weather_owm(city))
            else:
                raise ValueError("no OWM key")
        except Exception:
            try:
                lines.append(get_weather_wttr(city))
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
    r = requests.get(url, timeout=20)
    print(f"CallMeBot: {r.status_code} | {r.text[:200]}")
    return r.status_code == 200

# ─── التجميع والإرسال ────────────────────────────────────────
def main():
    now    = datetime.now().strftime("%A، %d %B %Y — %I:%M %p")
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
