import urllib.request
import json
import os
from datetime import datetime

TOKEN   = os.environ.get("TELEGRAM_TOKEN", "8937123757:AAEKKqNkosJc0WSK5hOigNboKmejd5QwKTM")
CHAT_ID = 22039859

hour_utc = datetime.utcnow().hour
hour_kw  = (hour_utc + 3) % 24   # Kuwait UTC+3

MSGS = {
    7:  "🌅 صباح الخير هادي!\n💧 الكوب الأول — ابدأ يومك بالماء!\nهدفك اليوم: 3 لتر (12 كوب × 250 مل) 🎯",
    11: "☀️ الساعة 11 صباحاً\n💧 حان وقت الكوب الثالث!\nالماء يزيد التركيز ويحرق الدهون 💪",
    15: "🌤️ الساعة 3 مساءً\n💧 نصف الطريق — الكوب السادس!\nلا تنسى جسمك يحتاج ترطيب مستمر",
    19: "🌇 المساء — الكوب التاسع 💧\nاقتربت من الهدف — لا تتوقف الآن! 💪",
    23: "🌙 آخر تذكير لهذا اليوم هادي!\n💧 كيف كان يومك مع الماء؟\nحاول تكمّل الـ 3 لتر قبل النوم 😴",
    18: "🏋️ بعد التمرين — اشرب ماء الآن!\n💧 جسمك يحتاجه بعد المجهود\nكوبان على الأقل بعد التمرين",
    22: "🌙 تذكير أخير لهذا اليوم 💧\nكوب ماء قبل النوم يساعد على الاسترداد الليلي 💤",
}

msg = MSGS.get(hour_kw,
    f"💧 تذكير شرب الماء — الساعة {hour_kw:02d}:00 الكويت\n"
    f"هدفك 3 لتر يومياً — استمر! 💪")

url  = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = json.dumps({"chat_id": CHAT_ID, "text": msg}).encode("utf-8")
req  = urllib.request.Request(url, data=data,
       headers={"Content-Type": "application/json; charset=utf-8"})
urllib.request.urlopen(req)
print(f"✅ Water reminder sent — Kuwait {hour_kw:02d}:00")
