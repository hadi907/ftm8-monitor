import urllib.request
import json
import os
from datetime import datetime

TOKEN = os.environ.get("TELEGRAM_TOKEN", "8937123757:AAEKKqNkosJc0WSK5hOigNboKmejd5QwKTM")
CHAT_ID = "22039859"

hour = datetime.utcnow().hour

if hour == 5:
    msg = (
        "\U0001f305 صباح الخير هادي!\n\n"
        "حان وقت تمارينك الصباحية \U0001f4aa\n"
        "افتح تطبيق اللياقة وابدأ برنامج اليوم\n\n"
        "تذكّر:\n"
        "• لا تنخفض رأسك بسرعة\n"
        "• اشرب ماء قبل البدء \U0001f4a7"
    )
elif hour == 13:
    msg = (
        "☀️ مساء النشاط هادي!\n\n"
        "هل قمت بتمارينك اليوم؟ \U0001f3cb️\n"
        "لا تزال لديك فرصة — افتح التطبيق الآن\n\n"
        "هدفك اليومي: ٧٠٠٠ خطوة \U0001f45f"
    )
elif hour == 17:
    msg = (
        "\U0001f319 آخر تذكير لهذا اليوم هادي!\n\n"
        "إذا لم تتمرن بعد:\n"
        "✅ ١٥ دقيقة مشي خفيف تكفي\n"
        "✅ أو تمارين الأكتاف البسيطة بدون معدات\n\n"
        "داوم على عادتك \U0001f4aa"
    )
else:
    msg = f"⏰ تذكير تمارين اللياقة الساعة {hour} UTC \U0001f4aa"

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = json.dumps({"chat_id": CHAT_ID, "text": msg}).encode("utf-8")
req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json; charset=utf-8"})
urllib.request.urlopen(req)
print(f"Done - hour {hour}:00 UTC")
