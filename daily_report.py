import urllib.request
import json
import os
from datetime import datetime, timezone, timedelta

TOKEN   = os.environ.get("TELEGRAM_TOKEN", "")
CHAT_ID = 22039859

# الوقت الحالي بتوقيت الكويت
now_kw = datetime.now(timezone(timedelta(hours=3)))
day_name_ar = ["الاثنين", "الثلاثاء", "الأربعاء", "الخميس", "الجمعة", "السبت", "الأحد"]
day = day_name_ar[now_kw.weekday()]
date_str = now_kw.strftime("%d/%m/%Y")

# تحديد نوع اليوم
weekday = now_kw.weekday()  # 0=Mon, 6=Sun
is_rest_day = weekday in [0, 3]  # الاثنين والخميس = أيام خفيفة

if is_rest_day:
    water_target = 3
    water_cups   = 3
    exercise_type = "يوم خفيف 🧘 (مشي + إطالة)"
else:
    water_target = 3.0
    water_cups   = 9
    exercise_type = "تمرين كامل 🏋️"

msg = f"""📊 تقرير نهاية اليوم — {day} {date_str}
{'─' * 30}

💧 الماء اليوم:
   • الهدف: {water_target} لتر ({water_cups} كوب × 200 مل)
   • هل أكملت الهدف؟ ✅ أو ❌

🏋️ التمرين اليوم:
   • النوع: {exercise_type}
   • هل تمرنت اليوم؟ ✅ أو ❌

📈 تذكير الغد:
   • ابدأ بكوب ماء فور الاستيقاظ 💧
   • جهّز ملابس التمرين الليلة 👟

{'─' * 30}
💪 كل يوم خطوة نحو الهدف هادي!"""

url  = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = json.dumps({"chat_id": CHAT_ID, "text": msg}).encode("utf-8")
req  = urllib.request.Request(url, data=data,
       headers={"Content-Type": "application/json; charset=utf-8"})
urllib.request.urlopen(req)
print(f"✅ Daily report sent — {date_str}")
