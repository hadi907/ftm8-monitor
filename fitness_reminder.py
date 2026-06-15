import urllib.request
import json
import os
from datetime import datetime

TOKEN = os.environ.get("TELEGRAM_TOKEN", "8937123757:AAEKKqNkosJc0WSK5hOigNboKmejd5QwKTM")
CHAT_ID = "22039859"

hour = datetime.utcnow().hour

if hour == 5:
    msg = "🌅 صباح الخير هادي!\n\nحان وقت تمارينك الصباحية 💪\nافتح تطبيق اللياقة وابدأ برنامج اليوم\n\nتذكّر:\n• لا تنخفض رأسك بسرعة\n• اشرب ماء قبل البدء 💧"
elif hour == 13:
    msg = "☀️ مساء النشاط هادي!\n\nهل قمت بتمارينك اليوم؟ 🏋️\nلا تزال لديك فرصة — افتح التطبيق الآن\n\nهدفك اليومي: ٧٠٠٠ خطوة 👟"
elif hour == 17:
    msg = "🌙 آخر تذكير لهذا اليوم هادي!\n\nإذا لم تتمرن بعد:\n✅ ١٥ دقيقة مشي خفيف تكفي\n✅ أو تمارين الأكتاف البسيطة بدون معدات\n\nداوم على عادتك 💪"
else:
    msg = f"⏰ تذكير تمارين اللياقة الساعة {hour} UTC 💪"

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = json.dumps({"chat_id": CHAT_ID, "text": msg}).encode("utf-8")
req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json; charset=utf-8"})
urllib.request.urlopen(req)
print(f"Done - hour {hour}:00 UTC")
