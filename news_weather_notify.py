import os
import requests
import urllib.parse
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta

# ─── الإعدادات ────────────────────────────────────────────────
OWM_API_KEY      = os.environ.get("OWM_API_KEY", "").strip()
TELEGRAM_TOKEN   = os.environ.get("TELEGRAM_TOKEN", "").strip()
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

CITIES = [
    {"name": "الأحمدي", "q_owm": "Al Ahmadi,KW",  "q_wttr": "Al-Ahmadi"},
    {"name": "الوفرة",  "q_owm": "Al Wafra,KW",   "q_wttr": "Al-Wafra"},
]

# المصادر مع تصنيفها
NEWS_SOURCES = [
    # 🇰🇼 أخبار الكويت
    {"name": "أخبار الكويت",     "url": "https://news.google.com/rss/search?q=الكويت&hl=ar&gl=KW&ceid=KW:ar",          "cat": "kw"},
    {"name": "KUNA",             "url": "https://www.kuna.net.kw/rss/rssfeeds.aspx?l=ar",                               "cat": "kw"},
    {"name": "القبس",            "url": "https://www.alqabas.com/feed/",                                                "cat": "kw"},
    {"name": "الأنباء",          "url": "https://www.alanba.com.kw/rss/",                                               "cat": "kw"},
    {"name": "الجريدة الكويتية", "url": "https://www.aljarida.com/feed/",                                               "cat": "kw"},
    {"name": "الراي",            "url": "https://www.alraimedia.com/feed/",                                             "cat": "kw"},
    # 🌍 عالمية
    {"name": "BBC عربي",         "url": "https://feeds.bbci.co.uk/arabic/rss.xml",                                      "cat": "world"},
    {"name": "سكاي نيوز",        "url": "https://www.skynewsarabia.com/rss.xml",                                        "cat": "world"},
    {"name": "RT عربي",          "url": "https://arabic.rt.com/rss/",                                                   "cat": "world"},
    # 💰 اقتصاد
    {"name": "اقتصاد الكويت",    "url": "https://news.google.com/rss/search?q=اقتصاد+الكويت&hl=ar&gl=KW&ceid=KW:ar",  "cat": "economy"},
    {"name": "CNBC عربية",       "url": "https://arabic.cnbc.com/rss/feeds/",                                           "cat": "economy"},
    # 💻 تقنية
    {"name": "تقنية",            "url": "https://news.google.com/rss/search?q=تقنية+ذكاء+اصطناعي&hl=ar&gl=KW&ceid=KW:ar", "cat": "tech"},
]

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
    cur  = d["current_condition"][0]
    temp = cur["temp_C"]; feels = cur["FeelsLikeC"]
    humidity = cur["humidity"]; wind = cur["windspeedKmph"]
    desc = cur["weatherDesc"][0]["value"]
    code = int(cur["weatherCode"])
    icon = ("☀️" if code == 113 else "⛅" if code in [116,119,122] else
            "🌧️" if code >= 263 else "🌡️")
    return (f"{icon} *{city['name']}:* {temp}°م (يبدو {feels}°م)\n"
            f"   💧 {humidity}%  💨 {wind} كم/س  | {desc}")

def get_weather():
    lines = ["☁️ *الطقس الآن*"]
    for city in CITIES:
        try:
            lines.append(get_weather_owm(city) if OWM_API_KEY else (_ for _ in ()).throw(ValueError()))
        except Exception:
            try:
                lines.append(get_weather_wttr(city))
            except Exception:
                lines.append(f"⚠️ {city['name']}: تعذّر جلب الطقس")
    return "\n".join(lines)

# ─── جلب الأخبار ─────────────────────────────────────────────
def fetch_titles(src, limit):
    titles = []
    try:
        r = requests.get(src["url"], timeout=10, headers={"User-Agent": "Mozilla/5.0"})
        root = ET.fromstring(r.content)
        for item in root.findall(".//item")[:limit*2]:
            t = item.findtext("title","").strip()
            if t:
                titles.append((src["name"], t))
            if len(titles) >= limit:
                break
    except Exception:
        pass
    return titles

def get_news():
    seen = set()
    sections = []

    # 🇰🇼 أخبار الكويت — 15 خبر من كل المصادر الكويتية
    kw_items = []
    for src in [s for s in NEWS_SOURCES if s["cat"] == "kw"]:
        for name, title in fetch_titles(src, 5):
            key = title[:30]
            if key not in seen:
                seen.add(key)
                kw_items.append((name, title))
        if len(kw_items) >= 15:
            break

    if kw_items:
        lines = ["\n🇰🇼 *أخبار الكويت*"]
        for i, (src, title) in enumerate(kw_items[:15], 1):
            lines.append(f"{i}. {title} _{src}_")
        sections.append("\n".join(lines))

    # باقي الفئات — 2 خبر لكل فئة
    categories = [
        ("world",   "🌍 *عالمية*"),
        ("economy", "💰 *اقتصاد*"),
        ("tech",    "💻 *تقنية*"),
    ]
    for cat, label in categories:
        items = []
        for src in [s for s in NEWS_SOURCES if s["cat"] == cat]:
            for name, title in fetch_titles(src, 3):
                key = title[:30]
                if key not in seen:
                    seen.add(key)
                    items.append((name, title))
                if len(items) >= 2:
                    break
            if len(items) >= 2:
                break
        if items:
            lines = [f"\n{label}"]
            for i, (src, title) in enumerate(items[:2], 1):
                lines.append(f"{i}. {title} _{src}_")
            sections.append("\n".join(lines))

    return "📰 *أبرز الأخبار*\n" + "\n".join(sections)

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
