import urllib.request
import json
import os
from datetime import datetime

# يمكن تخزين هذه القيم كـ Secrets في GitHub
TOKEN = os.environ.get("TELEGRAM_TOKEN", "8937123757:AAEKKqNkosJc0WSK5hOigNboKmejd5QwKTM")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "22039859")

hour = datetime.utcnow().hour  # GitHub Actions يستخدم UTC

if hour == 5:   # 8am بتوقيت السعودية (UTC+3)
    msg = (
        "🌅 صباح الخير هادي!\n\n"
        "حان وقت تمارينك الصباحية 💪\n"
        "افتح تطبيق اللياقة وابدأ برنامج اليوم\n\n"
        "تذكّر:\n"
        "• لا تنخفض رأسك بسرعة\n"
        "• اشرب ماء قبل البدء 💧"
    )
elif hour == 13:  # 4pm بتوقيت السعودية (UTC+3)
    msg = (
        "☀️ مساء النشاط هادي!\n\n"
        "هل قمت بتمارينك اليوم؟ 🏋️\n"
        "لا تزال لديك فرصة — افتح التطبيق الآن\n\n"
        "هدفك اليومي: ٧٠٠٠ خطوة 👟"
    )
elif hour == 17:  # 8pm بتوقيت السعودية (UTC+3)
    msg = (
        "🌙 آخر تذكير لهذا اليوم هادي!\n\n"
        "إذا لم تتمرن بعد:\n"
        "✅ ١٥ دقيقة مشي خفيف تكفي\n"
        "✅ أو تمارين الأكتاف البسيطة بدون معدات\n\n"
        "داوم على عادتك 💪"
    )
else:
    msg = f"⏰ تذكير تمارين اللياقة الساعة {hour} UTC 💪"

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = json.dumps({"chat_id": CHAT_ID, "text": msg}).encode("utf-8")
req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json; charset=utf-8"})
urllib.request.urlopen(req)
print(f"✅ تم إرسال التذكير - الساعة {hour}:00 UTC")
